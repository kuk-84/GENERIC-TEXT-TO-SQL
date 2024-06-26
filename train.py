# Apache License v2.0

# Tong Guo
# Sep30, 2019


import os, sys, argparse, re, json

from matplotlib.pylab import *
import torch.nn as nn
import torch
import torch.nn.functional as F
import random as python_random
# import torchvision.datasets as dsets

# BERT
import bert.tokenization as tokenization
from bert.modeling import BertConfig, BertModel

from sqlova.utils.utils_wikisql import *
from sqlova.utils.utils import load_jsonl
from sqlova.utils.utils import load_jsonl_ctable
from sqlova.model.nl2sql.wikisql_models import *
from sqlnet.dbengine import DBEngine

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def construct_hyper_param(parser):
    #parser.add_argument("--do_train", default=False)
    parser.add_argument('--do_infer', default=False)
    #parser.add_argument('--infer_loop', default=False)

    #parser.add_argument("--trained", default=True)
    
    parser.add_argument('--fine_tune',
                        default=True,
                        help="If present, BERT is trained.")
    
    parser.add_argument('--tepoch', default=1, type=int)#200
    parser.add_argument("--bS", default=8, type=int,#8
                        help="Batch size")
    parser.add_argument("--accumulate_gradients", default=1, type=int,
                        help="The number of accumulation of backpropagation to effectivly increase the batch size.")
    

    parser.add_argument("--model_type", default='Seq2SQL_v1', type=str,
                        help="Type of model.")

    # 1.2 BERT Parameters
    parser.add_argument("--vocab_file",
                        default='vocab.txt', type=str,
                        help="The vocabulary file that the BERT model was trained on.")
    parser.add_argument("--max_seq_length",
                        default=222, type=int,  # Set based on maximum length of input tokens.
                        help="The maximum total input sequence length after WordPiece tokenization. Sequences "
                             "longer than this will be truncated, and sequences shorter than this will be padded.")
    parser.add_argument("--num_target_layers",
                        default=2, type=int,
                        help="The Number of final layers of BERT to be used in downstream task.")
    parser.add_argument('--lr_bert', default=1e-5, type=float, help='BERT model learning rate.')
    parser.add_argument('--seed',
                        type=int,
                        default=42,
                        help="random seed for initialization")
    parser.add_argument('--no_pretraining', default=False, help='Use BERT pretrained model')
    parser.add_argument("--bert_type_abb", default='uS', type=str,
                        help="Type of BERT model to load. e.g.) uS, uL, cS, cL, and mcS")

    # 1.3 Seq-to-SQL module parameters
    parser.add_argument('--lS', default=2, type=int, help="The number of LSTM layers.")
    parser.add_argument('--dr', default=0.3, type=float, help="Dropout rate.")
    parser.add_argument('--lr', default=1e-3, type=float, help="Learning rate.")
    parser.add_argument("--hS", default=100, type=int, help="The dimension of hidden vector in the seq-to-SQL module.")

    # 1.4 Execution-guided decoding beam-size. It is used only in test.py
    parser.add_argument('--EG',
                        default=False,
                        help="If present, Execution guided decoding is used in test.")
    parser.add_argument('--beam_size',
                        type=int,
                        default=4,
                        help="The size of beam for smart decoding")

    args = parser.parse_args()

    map_bert_type_abb = {'uS': 'uncased_L-12_H-768_A-12',
                         'uL': 'uncased_L-24_H-1024_A-16',
                         'cS': 'cased_L-12_H-768_A-12',
                         'cL': 'cased_L-24_H-1024_A-16',
                         'mcS': 'multi_cased_L-12_H-768_A-12'}
    args.bert_type = map_bert_type_abb[args.bert_type_abb]
    print(f"BERT-type: {args.bert_type}")

    # Decide whether to use lower_case.
    if args.bert_type_abb == 'cS' or args.bert_type_abb == 'cL' or args.bert_type_abb == 'mcS':
        args.do_lower_case = False
    else:
        args.do_lower_case = True

    # Seeds for random number generation
    seed(args.seed)
    python_random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)

    # args.toy_model = not torch.cuda.is_available()
    args.toy_model = False
    args.toy_size = 12

    return args


def get_bert(BERT_PT_PATH, bert_type, do_lower_case, no_pretraining):
    bert_config_file = os.path.join(BERT_PT_PATH, f'bert_config_{bert_type}.json')
    #bert_config_file="C:/Users/sakshi/Downloads/NLP-SQL-Bert/data_and_model/bert_config_uncased_L-12_H-768_A-12.json"

    vocab_file = os.path.join(BERT_PT_PATH, f'vocab_{bert_type}.txt')
    #vocab_file="C:/Users/sakshi/Downloads/NLP-SQL-Bert/data_and_model/vocab_uncased_L-12_H-768_A-12.txt"
    init_checkpoint = os.path.join(BERT_PT_PATH, f'pytorch_model_{bert_type}.bin')
    #init_checkpoint="C:/Users/sakshi/Downloads/NLP-SQL-Bert/data_and_model/pytorch_model_uncased_L-12_H-768_A-12.bin"

    bert_config = BertConfig.from_json_file(bert_config_file)
    tokenizer = tokenization.FullTokenizer(
        vocab_file=vocab_file, do_lower_case=do_lower_case)
    bert_config.print_status()

    model_bert = BertModel(bert_config)
    if no_pretraining:
        pass
    else:
        model_bert.load_state_dict(torch.load(init_checkpoint, map_location='cpu'))
        print("Load pre-trained parameters.")
    model_bert.to(device)

    return model_bert, tokenizer, bert_config


def get_opt(model, model_bert, fine_tune):
    if fine_tune:
        opt = torch.optim.Adam(filter(lambda p: p.requires_grad, model.parameters()),
                               lr=args.lr, weight_decay=0)

        opt_bert = torch.optim.Adam(filter(lambda p: p.requires_grad, model_bert.parameters()),
                                    lr=args.lr_bert, weight_decay=0)
    else:
        opt = torch.optim.Adam(filter(lambda p: p.requires_grad, model.parameters()),
                               lr=args.lr, weight_decay=0)
        opt_bert = None

    return opt, opt_bert


def get_models(args, BERT_PT_PATH, trained=False, path_model_bert=None, path_model=None):
    # some constants
    agg_ops = ['', 'MAX', 'MIN', 'COUNT', 'SUM', 'AVG']
    cond_ops = ['=', '>', '<', 'OP']  # do not know why 'OP' required. Hence,

    print(f"Batch_size = {args.bS * args.accumulate_gradients}")
    print(f"BERT parameters:")
    print(f"learning rate: {args.lr_bert}")
    print(f"Fine-tune BERT: {args.fine_tune}")

    # Get BERT
    model_bert, tokenizer, bert_config = get_bert(BERT_PT_PATH, args.bert_type, args.do_lower_case,
                                                  args.no_pretraining)
    args.iS = bert_config.hidden_size * args.num_target_layers  # Seq-to-SQL input vector dimenstion

    # Get Seq-to-SQL

    n_cond_ops = len(cond_ops)
    n_agg_ops = len(agg_ops)
    print(f"Seq-to-SQL: the number of final BERT layers to be used: {args.num_target_layers}")
    print(f"Seq-to-SQL: the size of hidden dimension = {args.hS}")
    print(f"Seq-to-SQL: LSTM encoding layer size = {args.lS}")
    print(f"Seq-to-SQL: dropout rate = {args.dr}")
    print(f"Seq-to-SQL: learning rate = {args.lr}")
    model = Seq2SQL_v1(args.iS, args.hS, args.lS, args.dr, n_cond_ops, n_agg_ops)
    model = model.to(device)

    if trained:
        assert path_model_bert != None
        assert path_model != None

        if torch.cuda.is_available():
            res = torch.load(path_model_bert)
        else:
            res = torch.load(path_model_bert, map_location='cpu')
        model_bert.load_state_dict(res['model_bert'])
        model_bert.to(device)

        if torch.cuda.is_available():
            res = torch.load(path_model)
        else:
            res = torch.load(path_model, map_location='cpu')

        model.load_state_dict(res['model'])

    return model, model_bert, tokenizer, bert_config


def get_data(path_wikisql, args):
    train_data, train_table, dev_data, dev_table, _, _ = load_wikisql(path_wikisql, args.toy_model, args.toy_size,
                                                                      no_w2i=True, no_hs_tok=True)
    train_loader, dev_loader = get_loader_wikisql(train_data, dev_data, args.bS, shuffle_train=True)

    return train_data, train_table, dev_data, dev_table, train_loader, dev_loader

def load_wikisql_data_ctable(path_wikisql, mode='ctable', no_hs_tok=False, aug=False):
    data = []
    table = {}
    path_sql="C:/Users/sakshi/Downloads/NLP-SQL-Bert/data_and_model/ctable_tok.jsonl"
    path_table="C:/Users/sakshi/Downloads/NLP-SQL-Bert/data_and_model/ctable_tok.tables.jsonl"
    with open(path_sql,mode="r",encoding="utf-8") as f:
        t1 = json.load(f)
        data.append(t1)
    with open(path_table,mode="r",encoding="utf-8") as f:
        t1=json.load(f)
        table[t1['id']] = t1
    return data, table

def load_wikisql_ctable(path_wikisql, bert=False, no_w2i=False, no_hs_tok=False, aug=False):
    # Get data
    ctable_data, ctable_table = load_wikisql_data_ctable(path_wikisql, mode='ctable', no_hs_tok=no_hs_tok, aug=aug)
    # Get word vector
    if no_w2i:
        w2i, wemb = None, None
    else:
        w2i, wemb = load_w2i_wemb(path_wikisql, bert)

    return ctable_data, ctable_table

def get_loader_wikisql_ctable(data_ctable):
    ctable_loader = torch.utils.data.DataLoader(
        dataset=data_ctable,
    )

    return ctable_loader
def get_data_ctable(path_wikisql):
    ctable_data, ctable_table= load_wikisql_ctable(path_wikisql,no_w2i=True,no_hs_tok=True)
    ctable_loader = get_loader_wikisql_ctable(ctable_data)

    return ctable_data, ctable_table, ctable_loader

def train(train_loader, train_table, model, model_bert, opt, bert_config, tokenizer,
          max_seq_length, num_target_layers, accumulate_gradients=1, check_grad=True,
          st_pos=0, opt_bert=None, path_db=None, dset_name='train'):
    model.train()
    model_bert.train()

    ave_loss = 0
    cnt = 0  # count the # of examples
    cnt_sc = 0  # count the # of correct predictions of select column
    cnt_sa = 0  # of selectd aggregation
    cnt_wn = 0  # of where number
    cnt_wc = 0  # of where column
    cnt_wo = 0  # of where operator
    cnt_wv = 0  # of where-value
    cnt_wvi = 0  # of where-value index (on question tokens)
    cnt_lx = 0  # of logical form acc
    cnt_x = 0  # of execution acc

    # Engine for SQL querying.
    #engine = DBEngine(os.path.join(path_db, f"{dset_name}.db"))
    print(f"first db engine object creating from {dset_name}")
    engine = DBEngine(f"C:/Users/sakshi/Downloads/NLP-SQL-Bert/data_and_model/{dset_name}.db")
    engine.show_all_tables()
    
    for iB, t in enumerate(train_loader):
        print("inside trainloader")
        print(iB)
        print(t)
        cnt += len(t)

        if cnt < st_pos:
            continue

        # Get fields
        nlu, nlu_t, sql_i, sql_q, sql_t, tb, hs_t, hds = get_fields(t, train_table, no_hs_t=True, no_sql_t=True)
        # nlu  : natural language utterance
        # nlu_t: tokenized nlu
        # sql_i: canonical form of SQL query
        # sql_q: full SQL query text. Not used.
        # sql_t: tokenized SQL query
        # tb   : table
        # hs_t : tokenized headers. Not used.

        g_sc, g_sa, g_wn, g_wc, g_wo, g_wv = get_g(sql_i)
        # get ground truth where-value index under CoreNLP tokenization scheme. It's done already on trainset.
        g_wvi_corenlp = get_g_wvi_corenlp(t)

        wemb_n, wemb_h, l_n, l_hpu, l_hs, \
        nlu_tt, t_to_tt_idx, tt_to_t_idx \
            = get_wemb_bert(bert_config, model_bert, tokenizer, nlu_t, hds, max_seq_length,
                            num_out_layers_n=num_target_layers, num_out_layers_h=num_target_layers)

        # wemb_n: natural language embedding
        # wemb_h: header embedding
        # l_n: token lengths of each question
        # l_hpu: header token lengths
        # l_hs: the number of columns (headers) of the tables.
        try:
            #
            g_wvi = get_g_wvi_bert_from_g_wvi_corenlp(t_to_tt_idx, g_wvi_corenlp)
        except:
            # Exception happens when where-condition is not found in nlu_tt.
            # In this case, that train example is not used.
            # During test, that example considered as wrongly answered.
            # e.g. train: 32.
            continue

        knowledge = []
        for k in t:
            if "bertindex_knowledge" in k:
                knowledge.append(k["bertindex_knowledge"])
                
            else:
                knowledge.append(max(l_n)*[0])

        print("knowledge")
        print(knowledge)

        knowledge_header = []
        for k in t:
            if "header_knowledge" in k:
                knowledge_header.append(k["header_knowledge"])
                
            else:
                knowledge_header.append(max(l_hs) * [0])
        print("knowledge header")
        print(knowledge_header)
        # score
        s_sc, s_sa, s_wn, s_wc, s_wo, s_wv = model(wemb_n, l_n, wemb_h, l_hpu, l_hs,
                                                   g_sc=g_sc, g_sa=g_sa, g_wn=g_wn, g_wc=g_wc, g_wvi=g_wvi,
                                                   knowledge = knowledge,
                                                   knowledge_header = knowledge_header)

        # Calculate loss & step
        loss = Loss_sw_se(s_sc, s_sa, s_wn, s_wc, s_wo, s_wv, g_sc, g_sa, g_wn, g_wc, g_wo, g_wvi)
        print("loss")
        print(loss)

        # Calculate gradient
        if iB % accumulate_gradients == 0:  # mode
            # at start, perform zero_grad
            opt.zero_grad()
            if opt_bert:
                opt_bert.zero_grad()
            loss.backward()
            if accumulate_gradients == 1:
                opt.step()
                if opt_bert:
                    opt_bert.step()
        elif iB % accumulate_gradients == (accumulate_gradients - 1):
            # at the final, take step with accumulated graident
            loss.backward()
            opt.step()
            if opt_bert:
                opt_bert.step()
        else:
            # at intermediate stage, just accumulates the gradients
            loss.backward()

        # Prediction
        pr_sc, pr_sa, pr_wn, pr_wc, pr_wo, pr_wvi = pred_sw_se(s_sc, s_sa, s_wn, s_wc, s_wo, s_wv, )
        pr_wv_str, pr_wv_str_wp = convert_pr_wvi_to_string(pr_wvi, nlu_t, nlu_tt, tt_to_t_idx, nlu)

        # Sort pr_wc:
        #   Sort pr_wc when training the model as pr_wo and pr_wvi are predicted using ground-truth where-column (g_wc)
        #   In case of 'dev' or 'test', it is not necessary as the ground-truth is not used during inference.
        pr_wc_sorted = sort_pr_wc(pr_wc, g_wc)
        pr_sql_i = generate_sql_i(pr_sc, pr_sa, pr_wn, pr_wc_sorted, pr_wo, pr_wv_str, nlu)

        # Cacluate accuracy
        cnt_sc1_list, cnt_sa1_list, cnt_wn1_list, \
        cnt_wc1_list, cnt_wo1_list, \
        cnt_wvi1_list, cnt_wv1_list = get_cnt_sw_list(g_sc, g_sa, g_wn, g_wc, g_wo, g_wvi,
                                                      pr_sc, pr_sa, pr_wn, pr_wc, pr_wo, pr_wvi,
                                                      sql_i, pr_sql_i,
                                                      nlu,tb,
                                                      mode='train')

        cnt_lx1_list = get_cnt_lx_list(cnt_sc1_list, cnt_sa1_list, cnt_wn1_list, cnt_wc1_list,
                                       cnt_wo1_list, cnt_wv1_list)
        # lx stands for logical form accuracy

        # Execution accuracy test.
        cnt_x1_list, g_ans, pr_ans = get_cnt_x_list(engine, tb, g_sc, g_sa, sql_i, pr_sc, pr_sa, pr_sql_i)

        # statistics
        ave_loss += loss.item()

        # count
        cnt_sc += sum(cnt_sc1_list)
        cnt_sa += sum(cnt_sa1_list)
        cnt_wn += sum(cnt_wn1_list)
        cnt_wc += sum(cnt_wc1_list)
        cnt_wo += sum(cnt_wo1_list)
        cnt_wvi += sum(cnt_wvi1_list)
        cnt_wv += sum(cnt_wv1_list)
        cnt_lx += sum(cnt_lx1_list)
        cnt_x += sum(cnt_x1_list)

    ave_loss /= cnt
    acc_sc = cnt_sc / cnt
    acc_sa = cnt_sa / cnt
    acc_wn = cnt_wn / cnt
    acc_wc = cnt_wc / cnt
    acc_wo = cnt_wo / cnt
    acc_wvi = cnt_wvi / cnt
    acc_wv = cnt_wv / cnt
    acc_lx = cnt_lx / cnt
    acc_x = cnt_x / cnt

    acc = [ave_loss, acc_sc, acc_sa, acc_wn, acc_wc, acc_wo, acc_wvi, acc_wv, acc_lx, acc_x]
    print(accuracy)
    print(acc)

    aux_out = 1
    for iB, t in enumerate(train_loader):
    # Your existing code here
    
    # print statements to display accuracy and other statistics
        print(f"Step {iB + 1}:")
        print(f"Average Loss: {ave_loss}")
        print(f"Select Column Accuracy: {acc_sc}")
        print(f"Select Aggregation Accuracy: {acc_sa}")
        print(f"Where Number Accuracy: {acc_wn}")
        print(f"Where Column Accuracy: {acc_wc}")
        print(f"Where Operator Accuracy: {acc_wo}")
        print(f"Where-Value Index Accuracy: {acc_wvi}")
        print(f"Where-Value Accuracy: {acc_wv}")
        print(f"Logical Form Accuracy: {acc_lx}")
        print(f"Execution Accuracy: {acc_x}")


    return acc, aux_out


def report_detail(hds, nlu,
                  g_sc, g_sa, g_wn, g_wc, g_wo, g_wv, g_wv_str, g_sql_q, g_ans,
                  pr_sc, pr_sa, pr_wn, pr_wc, pr_wo, pr_wv_str, pr_sql_q, pr_ans,
                  cnt_list, current_cnt):
    cnt_tot, cnt, cnt_sc, cnt_sa, cnt_wn, cnt_wc, cnt_wo, cnt_wv, cnt_wvi, cnt_lx, cnt_x = current_cnt

    print(f'cnt = {cnt} / {cnt_tot} ===============================')

    print(f'headers: {hds}')
    print(f'nlu: {nlu}')

    # print(f's_sc: {s_sc[0]}')
    # print(f's_sa: {s_sa[0]}')
    # print(f's_wn: {s_wn[0]}')
    # print(f's_wc: {s_wc[0]}')
    # print(f's_wo: {s_wo[0]}')
    # print(f's_wv: {s_wv[0][0]}')
    print(f'===============================')
    print(f'g_sc : {g_sc}')
    print(f'pr_sc: {pr_sc}')
    print(f'g_sa : {g_sa}')
    print(f'pr_sa: {pr_sa}')
    print(f'g_wn : {g_wn}')
    print(f'pr_wn: {pr_wn}')
    print(f'g_wc : {g_wc}')
    print(f'pr_wc: {pr_wc}')
    print(f'g_wo : {g_wo}')
    print(f'pr_wo: {pr_wo}')
    print(f'g_wv : {g_wv}')
    # print(f'pr_wvi: {pr_wvi}')
    print('g_wv_str:', g_wv_str)
    print('p_wv_str:', pr_wv_str)
    print(f'g_sql_q:  {g_sql_q}')
    print(f'pr_sql_q: {pr_sql_q}')
    print(f'g_ans: {g_ans}')
    print(f'pr_ans: {pr_ans}')
    print(f'--------------------------------')

    print(cnt_list)

    print(f'acc_lx = {cnt_lx / cnt:.3f}, acc_x = {cnt_x / cnt:.3f}\n',
          f'acc_sc = {cnt_sc / cnt:.3f}, acc_sa = {cnt_sa / cnt:.3f}, acc_wn = {cnt_wn / cnt:.3f}\n',
          f'acc_wc = {cnt_wc / cnt:.3f}, acc_wo = {cnt_wo / cnt:.3f}, acc_wv = {cnt_wv / cnt:.3f}')
    print(f'===============================')

#data_loader
def test(t, data_table, model, model_bert, bert_config, tokenizer,
         max_seq_length,
         num_target_layers, detail=False, st_pos=0, cnt_tot=1, EG=False, beam_size=4,
         path_db=None, dset_name='test'):
    model.eval()
    model_bert.eval()

    ave_loss = 0
    cnt = 0
    cnt_sc = 0
    cnt_sa = 0
    cnt_wn = 0
    cnt_wc = 0
    cnt_wo = 0
    cnt_wv = 0
    cnt_wvi = 0
    cnt_lx = 0
    cnt_x = 0

    cnt_list = []

    #engine = DBEngine(os.path.join(path_db, f"{dset_name}.db"))
    engine = DBEngine(f"C:/Users/sakshi/Downloads/NLP-SQL-Bert/data_and_model/{dset_name}.db")
    results = []
    #for iB, t in enumerate(data_loader):
    #print(iB)
    #print(t)
    # cnt += len(t)
    # if cnt < st_pos:
    #     continue
    # Get fields
    # t=[{'table_id': '1-10015132-11', 'phase': 1, 'question': 'What position does the player who played for butler cc (ks) play?', 'question_tok': ['What', 'position', 'does', 'the', 'player', 'who', 'played', 'for', 'butler', 'cc', '(', 'ks', ')', 'play', '?'], 'sql': {'sel': 3, 'conds': [[5, 0, 'Butler CC (KS)']], 'agg': 0}, 'query': {'sel': 3, 'conds': [[5, 0, 'Butler CC (KS)']], 'agg': 0}, 'wvi_corenlp': [[8, 12]], 'bertindex_knowledge': [0, 4, 0, 0, 4, 0, 0, 0, 1, 2, 2, 2, 3, 0, 0], 'header_knowledge': [1, 0, 0, 1, 0, 2]}]
    # nlu, nlu_t, sql_i, sql_q, sql_t, tb, hs_t, hds = get_fields(t, data_table, no_hs_t=True, no_sql_t=True)
    nlu, nlu_t, sql_t, tb, hs_t, hds = get_fields(t, data_table, no_hs_t=True, no_sql_t=True)
    

    # g_sc, g_sa, g_wn, g_wc, g_wo, g_wv = get_g(sql_i)
    # g_wvi_corenlp = get_g_wvi_corenlp(t)

    wemb_n, wemb_h, l_n, l_hpu, l_hs, \
    nlu_tt, t_to_tt_idx, tt_to_t_idx \
        = get_wemb_bert(bert_config, model_bert, tokenizer, nlu_t, hds, max_seq_length,
                        num_out_layers_n=num_target_layers, num_out_layers_h=num_target_layers)


    try:
        g_wvi = get_g_wvi_bert_from_g_wvi_corenlp(t_to_tt_idx, g_wvi_corenlp)
        g_wv_str, g_wv_str_wp = convert_pr_wvi_to_string(g_wvi, nlu_t, nlu_tt, tt_to_t_idx, nlu)

    except:
        # Exception happens when where-condition is not found in nlu_tt.
        # In this case, that train example is not used.
        # During test, that example considered as wrongly answered.
        for b in range(len(nlu)):
            results1 = {}
            results1["error"] = "Skip happened"
            results1["nlu"] = nlu[b]
            results1["table_id"] = tb[b]["id"]
            results.append(results1)
        #continue

    knowledge = []
    for k in t:
        if "bertindex_knowledge" in k:
            knowledge.append(k["bertindex_knowledge"])
        else:
            knowledge.append(max(l_n) * [0])

    knowledge_header = []
    for k in t:
        if "header_knowledge" in k:
            knowledge_header.append(k["header_knowledge"])
        else:
            knowledge_header.append(max(l_hs) * [0])

    # model specific part
    # score
    if not EG:
        print("wemb_n")
        print(wemb_n)
        print("l_n")
        print(l_n)
        print("wemb_h")
        print(wemb_h)
        print("l_hpu")
        print(l_hpu)
        print("l_hs")
        print(l_hs)
        print("engine")
        print(engine)
        print("tb")
        print(tb)
        print("nlu_t")
        print(nlu_t)
        print("nlu_tt")
        print(nlu_tt)
        print("tt_to_t_idx")
        print(tt_to_t_idx)
        # No Execution guided decoding
        s_sc, s_sa, s_wn, s_wc, s_wo, s_wv = model(wemb_n, l_n, wemb_h, l_hpu, l_hs,
                                                    knowledge=knowledge,
                                                    knowledge_header=knowledge_header)

        # get loss & step
        # loss = Loss_sw_se(s_sc, s_sa, s_wn, s_wc, s_wo, s_wv, g_sc, g_sa, g_wn, g_wc, g_wo, g_wvi)

        # prediction
        pr_sc, pr_sa, pr_wn, pr_wc, pr_wo, pr_wvi = pred_sw_se(s_sc, s_sa, s_wn, s_wc, s_wo, s_wv, )
        pr_wv_str, pr_wv_str_wp = convert_pr_wvi_to_string(pr_wvi, nlu_t, nlu_tt, tt_to_t_idx, nlu)
        # g_sql_i = generate_sql_i(g_sc, g_sa, g_wn, g_wc, g_wo, g_wv_str, nlu)
        pr_sql_i = generate_sql_i(pr_sc, pr_sa, pr_wn, pr_wc, pr_wo, pr_wv_str, nlu)
        print("pr_sql_i")
        print(pr_sql_i)
    else:
        # Execution guided decoding
        print("wemb_n")
        print(wemb_n)
        print("l_n")
        print(l_n)
        print("wemb_h")
        print(wemb_h)
        print("l_hpu")
        print(l_hpu)
        print("l_hs")
        print(l_hs)
        print("engine")
        print(engine)
        print("tb")
        print(tb)
        print("nlu_t")
        print(nlu_t)
        print("nlu_tt")
        print(nlu_tt)
        print("tt_to_t_idx")
        print(tt_to_t_idx)

        prob_sca, prob_w, prob_wn_w, pr_sc, pr_sa, pr_wn, pr_sql_i = model.beam_forward(wemb_n, l_n, wemb_h, l_hpu,
                                                                                        l_hs, engine, tb,
                                                                                        nlu_t, nlu_tt,
                                                                                        tt_to_t_idx, nlu,
                                                                                        beam_size=beam_size,
                                                    knowledge=knowledge,
                                                    knowledge_header=knowledge_header)
        # sort and generate

        print(prob_sca)
        print(prob_w)
        print(prob_wn_w)
        print(pr_sc)
        print(pr_sa)
        print(pr_wn)
       

        pr_wc, pr_wo, pr_wv, pr_sql_i = sort_and_generate_pr_w(pr_sql_i)
        

        # Follosing variables are just for the consistency with no-EG case.
        pr_wvi = None  # not used
        pr_wv_str = None
        pr_wv_str_wp = None
        loss = torch.tensor([0])

    #g_sql_q = generate_sql_q(sql_i, tb)
    pr_sql_q = generate_sql_q(pr_sql_i, tb)
    pr_ans = []
    pr_query=""
    for i in range(len(pr_sql_i)):
        try:
            # print("hello try")
            # print(tb[i]['id'])
            # print(pr_sc[i])
            # print(pr_sa[i])
            # print(pr_sql_i[i]['conds'])
            pr_ans_i, pr_query= engine.execute_return_query(tb[i]['id'], pr_sc[i], pr_sa[i], pr_sql_i[i]['conds'])
            # print("answer found")
            # print(pr_query)
            # print(pr_ans_i)
            for pr_ans_i_e in pr_ans_i:
                pr_ans.append(pr_ans_i_e)

        except:
            pr_ans.append('Answer not found.')
    
    #print(pr_ans)

    # Saving for the official evaluation later.
    for b, pr_sql_i1 in enumerate(pr_sql_i):
        results1 = {}
        results1["query"] = pr_sql_i1
        results1["table_id"] = tb[b]["id"]
        results1["nlu"] = nlu[b]
        results.append(results1)
        print("Question:", nlu[b])
        print("Generated SQL query:", pr_sql_i1)
    print(pr_query)
    print(pr_ans)
    
    # cnt_sc1_list, cnt_sa1_list, cnt_wn1_list, \
    # cnt_wc1_list, cnt_wo1_list, \
    # cnt_wvi1_list, cnt_wv1_list = get_cnt_sw_list(g_sc, g_sa, g_wn, g_wc, g_wo, g_wvi,
    #                                                 pr_sc, pr_sa, pr_wn, pr_wc, pr_wo, pr_wvi,
    #                                                 sql_i, pr_sql_i,
    #                                                 nlu,tb,
    #                                                 mode='test')

    # cnt_lx1_list = get_cnt_lx_list(cnt_sc1_list, cnt_sa1_list, cnt_wn1_list, cnt_wc1_list,
    #                                 cnt_wo1_list, cnt_wv1_list)

    # # Execution accura y test
    # cnt_x1_list = []
    # # lx stands for logical form accuracy

    # # Execution accuracy test.
    # cnt_x1_list, g_ans, pr_ans = get_cnt_x_list(engine, tb, g_sc, g_sa, sql_i, pr_sc, pr_sa, pr_sql_i)

    # # stat
    # ave_loss += loss.item()

    # # count
    # cnt_sc += sum(cnt_sc1_list)
    # cnt_sa += sum(cnt_sa1_list)
    # cnt_wn += sum(cnt_wn1_list)
    # cnt_wc += sum(cnt_wc1_list)
    # cnt_wo += sum(cnt_wo1_list)
    # cnt_wv += sum(cnt_wv1_list)
    # cnt_wvi += sum(cnt_wvi1_list)
    # cnt_lx += sum(cnt_lx1_list)
    # cnt_x += sum(cnt_x1_list)

    # current_cnt = [cnt_tot, cnt, cnt_sc, cnt_sa, cnt_wn, cnt_wc, cnt_wo, cnt_wv, cnt_wvi, cnt_lx, cnt_x]
    # cnt_list1 = [cnt_sc1_list, cnt_sa1_list, cnt_wn1_list, cnt_wc1_list, cnt_wo1_list, cnt_wv1_list, cnt_lx1_list,
    #                 cnt_x1_list]
    # cnt_list.append(cnt_list1)
    # # report
    # if detail:
    #     report_detail(hds, nlu,
    #                     g_sc, g_sa, g_wn, g_wc, g_wo, g_wv, g_wv_str, g_sql_q, g_ans,
    #                     pr_sc, pr_sa, pr_wn, pr_wc, pr_wo, pr_wv_str, pr_sql_q, pr_ans,
    #                     cnt_list1, current_cnt)
    # cnt=1
    # ave_loss /= cnt
    # acc_sc = cnt_sc / cnt
    # acc_sa = cnt_sa / cnt
    # acc_wn = cnt_wn / cnt
    # acc_wc = cnt_wc / cnt
    # acc_wo = cnt_wo / cnt
    # acc_wvi = cnt_wvi / cnt
    # acc_wv = cnt_wv / cnt
    # acc_lx = cnt_lx / cnt
    # acc_x = cnt_x / cnt

    # acc = [ave_loss, acc_sc, acc_sa, acc_wn, acc_wc, acc_wo, acc_wvi, acc_wv, acc_lx, acc_x]
    # print(acc)
    cnt_list=[]
    acc=0
    #return acc, results, cnt_list
    return pr_query,pr_ans



def tokenize_corenlp(client, nlu1):
    nlu1_tok = []
    for sentence in client.annotate(nlu1):
        for tok in sentence:
            nlu1_tok.append(tok.originalText)
    return nlu1_tok


def tokenize_corenlp_direct_version(client, nlu1):
    nlu1_tok = []
    for sentence in client.annotate(nlu1).sentence:
        for tok in sentence.token:
            nlu1_tok.append(tok.originalText)
    return nlu1_tok


def infer(nlu1,
          table_name, data_table, path_db, db_name,
          model, model_bert, bert_config, max_seq_length, num_target_layers,
          beam_size=4, show_table=False, show_answer_only=False):
    # I know it is of against the DRY principle but to minimize the risk of introducing bug w, the infer function introuced.
    model.eval()
    model_bert.eval()
    engine = DBEngine(os.path.join(path_db, f"{db_name}.db"))

    # Get inputs
    nlu = [nlu1]
    # nlu_t1 = tokenize_corenlp(client, nlu1)
    nlu_t1 = tokenize_corenlp_direct_version(client, nlu1)
    nlu_t = [nlu_t1]

    tb1 = data_table[0]
    hds1 = tb1['header']
    tb = [tb1]
    hds = [hds1]
    hs_t = [[]]
    t=[{"table_id": "1-ftable1", "phase": 1, "question": "How many employees does Company A have?", "question_tok": ["How", "many", "employees", "does", "Company", "A", "have", "?"], "bertindex_knowledge": [0, 0, 4, 0, 1, 3, 0, 0], "header_knowledge": [2, 1]}]
    knowledge = []
    for k in t:
        if "bertindex_knowledge" in k:
            knowledge.append(k["bertindex_knowledge"])
        else:
            knowledge.append(max(l_n) * [0])

    knowledge_header = []
    for k in t:
        if "header_knowledge" in k:
            knowledge_header.append(k["header_knowledge"])
        else:
            knowledge_header.append(max(l_hs) * [0])

    wemb_n, wemb_h, l_n, l_hpu, l_hs, \
    nlu_tt, t_to_tt_idx, tt_to_t_idx \
        = get_wemb_bert(bert_config, model_bert, tokenizer, nlu_t, hds, max_seq_length,
                        num_out_layers_n=num_target_layers, num_out_layers_h=num_target_layers)

    prob_sca, prob_w, prob_wn_w, pr_sc, pr_sa, pr_wn, pr_sql_i = model.beam_forward(wemb_n, l_n, wemb_h, l_hpu,
                                                                                    l_hs, engine, tb,
                                                                                    nlu_t, nlu_tt,
                                                                                    tt_to_t_idx, nlu,
                                                                                    beam_size=beam_size,knowledge=knowledge,knowledge_header=knowledge_header)

    # sort and generate
    pr_wc, pr_wo, pr_wv, pr_sql_i = sort_and_generate_pr_w(pr_sql_i)
    if len(pr_sql_i) != 1:
        raise EnvironmentError
    pr_sql_q1 = generate_sql_q(pr_sql_i, [tb1])
    pr_sql_q = [pr_sql_q1]

    try:
        pr_ans, _ = engine.execute_return_query(tb[0]['id'], pr_sc[0], pr_sa[0], pr_sql_i[0]['conds'])
    except:
        pr_ans = ['Answer not found.']
        pr_sql_q = ['Answer not found.']

    if show_answer_only:
        print(f'Q: {nlu[0]}')
        print(f'A: {pr_ans[0]}')
        print(f'SQL: {pr_sql_q}')

    else:
        print(f'START ============================================================= ')
        print(f'{hds}')
        if show_table:
            print(engine.show_table(table_name))
        print(f'nlu: {nlu}')
        print(f'pr_sql_i : {pr_sql_i}')
        print(f'pr_sql_q : {pr_sql_q}')
        print(f'pr_ans: {pr_ans}')
        print(f'---------------------------------------------------------------------')

    return pr_sql_i, pr_ans




def print_result(epoch, acc, dname):
    ave_loss, acc_sc, acc_sa, acc_wn, acc_wc, acc_wo, acc_wvi, acc_wv, acc_lx, acc_x = acc

    print(f'{dname} results ------------')
    print(
        f" Epoch: {epoch}, ave loss: {ave_loss}, acc_sc: {acc_sc:.3f}, acc_sa: {acc_sa:.3f}, acc_wn: {acc_wn:.3f}, \
        acc_wc: {acc_wc:.3f}, acc_wo: {acc_wo:.3f}, acc_wvi: {acc_wvi:.3f}, acc_wv: {acc_wv:.3f}, acc_lx: {acc_lx:.3f}, acc_x: {acc_x:.3f}"
    )

def get_result():
    parser = argparse.ArgumentParser()
    args = construct_hyper_param(parser)
    path_h = './data_and_model'  
    path_wikisql = './data_and_model'  
    BERT_PT_PATH = path_wikisql
    path_save_for_evaluation = './'
    train_data, train_table, dev_data, dev_table, train_loader, dev_loader =\
        get_data(path_wikisql, args)

    ctable_data,ctable_table,ctable_loader=get_data_ctable(path_wikisql)

    path_model_bert = './model_bert_best.pt'
    path_model = './model_best.pt'
    model, model_bert, tokenizer, bert_config = get_models(args, BERT_PT_PATH, trained=True,
                                                            path_model_bert=path_model_bert, path_model=path_model)

    data_list=[]
    with open("./data_and_model/ctable_knowledge.jsonl","r") as f:
        data_list = [json.loads(line) for line in f]
    #t=[{"table_id": "1-ftable3", "phase": 1, "question": "what is the sum of quantity of product b sold?", "question_tok": ["what", "is", "the", "sum", "of", "quantity", "of", "product", "b", "sold", "?"], "bertindex_knowledge": [3, 0, 0, 0, 0, 4, 0, 3, 3, 0, 0], "header_knowledge": [0, 2, 1]}]
    print(ctable_table)
    result=[]
    with torch.no_grad():
        #acc_dev, results_dev, cnt_list
        query,ans= test(data_list,
                                                ctable_table,
                                                model,
                                                model_bert,
                                                bert_config,
                                                tokenizer,
                                                args.max_seq_length,
                                                args.num_target_layers,
                                                detail=False,
                                                path_db=path_wikisql,
                                                st_pos=0,
                                                dset_name='ctable', EG=args.EG)
        result.extend((query, ans,ctable_table))
    return result

