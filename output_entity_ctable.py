
import sys
# caution: path[0] is reserved for script path (or '' in REPL)
sys.path.insert(1, 'C:/Users/sakshi/Downloads/NLP-SQL-Bert/sqlnet')

import dbengine
from dbengine import DBEngine

sys.path.insert(1, 'C:/Users/sakshi/Downloads/NLP-SQL-Bert/bert')
import tokenization as tokenization

import json
import torch
import os
import torch.utils.data
from matplotlib.pylab import *

def get_loader_wikisql_ctable(data_ctable):
    ctable_loader = torch.utils.data.DataLoader(
        dataset=data_ctable,
    )

    return ctable_loader

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


def load_w2i_wemb(path_wikisql, bert=False):
    """ Load pre-made subset of TAPI.
    """
    if bert:
        with open(os.path.join(path_wikisql, 'w2i_bert.json'), 'r') as f_w2i:
            w2i = json.load(f_w2i)
        wemb = load(os.path.join(path_wikisql, 'wemb_bert.npy'), )
    else:
        with open(os.path.join(path_wikisql, 'w2i.json'), 'r') as f_w2i:
            w2i = json.load(f_w2i)

        wemb = load(os.path.join(path_wikisql, 'wemb.npy'), )
    return w2i, wemb

# Load data -----------------------------------------------------------------------------------------------
def load_wikisql_ctable(path_wikisql, bert=False, no_w2i=False, no_hs_tok=False, aug=False):
    # Get data
    ctable_data, ctable_table = load_wikisql_data_ctable(path_wikisql, mode='ctable', no_hs_tok=no_hs_tok, aug=aug)
    # Get word vector
    if no_w2i:
        w2i, wemb = None, None
    else:
        w2i, wemb = load_w2i_wemb(path_wikisql, bert)

    return ctable_data, ctable_table

def get_data_ctable(path_wikisql):
    ctable_data, ctable_table= load_wikisql_ctable(path_wikisql,no_w2i=True,no_hs_tok=True)
    ctable_loader = get_loader_wikisql_ctable(ctable_data)

    return ctable_data, ctable_table, ctable_loader

#engine_train = DBEngine("train.db")
#engine_dev = DBEngine("dev.db")
ctable_data, ctable_table, ctable_loader = get_data_ctable("C:/Users/sakshi/Downloads/NLP-SQL-Bert/data_and_model")
count = 0
count_agg_0 = 0
count_agg_not_0 = 0

tokenizer = tokenization.FullTokenizer(
        vocab_file="C:/Users/sakshi/Downloads/NLP-SQL-Bert/data_and_model/vocab_uncased_L-12_H-768_A-12.txt", do_lower_case=True)


def contains2(small_str,big_str):
    if small_str in big_str:
        start = big_str.index(small_str)
        return True,start,start+len(small_str)-1
    else:
        return False,-1,-1

def contains(small_list,big_list):
    result = False
    for i,item in enumerate(big_list):
        if item == small_list[0]:
            result = True
            if i+len(small_list)>len(big_list):
                result = False
                break
            for ii in range(0,len(small_list)):
                if small_list[ii] != big_list[i+ii]:
                    result=False
                    break
                if ii == len(small_list)-1:
                    return result,i,i+ii
    return result,-1,-1
import re
re_ = re.compile(' ')
def process(data,table,output_name):  # sourcery skip: low-code-quality
  final_all = []
  badcase = 0
  print("in process")
  for i, one_data in enumerate(data):
    # if i<=368:
    #     continue
    nlu_t1 = one_data["question_tok"]
    print("nlu_t1",nlu_t1)
    # nlu_tt2 = tokenizer.tokenize(one_data["question"])

    # 1. 2nd tokenization using WordPiece
    charindex2wordindex = {}
    total = 0
    tt_to_t_idx1 = []  # number indicates where sub-token belongs to in 1st-level-tokens (here, CoreNLP).
    t_to_tt_idx1 = []  # orig_to_tok_idx[i] = start index of i-th-1st-level-token in all_tokens.
    nlu_tt1 = []  # all_doc_tokens[ orig_to_tok_idx[i] ] returns first sub-token segement of i-th-1st-level-token
    for (ii, token) in enumerate(nlu_t1):
        print(ii)
        print(token)
        t_to_tt_idx1.append(
            len(nlu_tt1))
        print("t_to_tt_idx1",t_to_tt_idx1)  # all_doc_tokens[ indicate the start position of original 'white-space' tokens.
        sub_tokens = tokenizer.tokenize(token)
        print("sub_tokens",sub_tokens)
        for sub_token in sub_tokens:
            tt_to_t_idx1.append(ii)
            nlu_tt1.append(sub_token)  # all_doc_tokens are further tokenized using WordPiece tokenizer

        token_ = re_.sub('',token)
        print(token_)
        for iii in range(len(token_)):
            charindex2wordindex[total+iii]=ii
        total += len(token_)
        print("total",total)
    print("charindex2wordindex",charindex2wordindex)
    print("nlu_tt1",nlu_tt1)
    one_final = one_data
    print(one_final)
    x=one_data['table_id']
    print(x)
    one_table = table[one_data['table_id']]
    print(one_table)
    final_question = [0] * len(nlu_tt1)
    print(final_question)
    one_final["bertindex_knowledge"] = final_question
    final_header = [0] * len(one_table["header"])
    print(final_header)
    one_final["header_knowledge"] = final_header
    for ii,h in enumerate(one_table["header"]):
        print(ii)
        print(h)
        h = h.lower()
        hs = h.split("/")
        for h_ in hs:
            flag, start_, end_ = contains2(re_.sub('', h_), "".join(one_data["question_tok"]).lower())
            print(flag)
            print(start_)
            print(end_)
            if flag == True:
                try:
                    start = t_to_tt_idx1[charindex2wordindex[start_]]
                    print(start)
                    end = t_to_tt_idx1[charindex2wordindex[end_]]
                    print(end)
                    for iii in range(start,end):
                        final_question[iii] = 4
                    final_question[start] = 4
                    final_question[end] = 4
                    one_final["bertindex_knowledge"] = final_question
                except:
                    print("!!!!!")
                    continue

    for ii,h in enumerate(one_table["header"]):
        h = h.lower()
        hs = h.split("/")
        print(ii)
        print(h)
        for h_ in hs:
            flag, start_, end_ = contains2(re_.sub('', h_), "".join(one_data["question_tok"]).lower())
            print(flag)
            print(start_)
            print(end_)
            if flag == True:
                try:
                    final_header[ii] = 1
                    break
                except:
                    print("!!!!")
                    continue

    for row in one_table["rows"]:
        print(row)
        for iiii, cell in enumerate(row):
            print(iiii)
            print(cell)
            cell = str(cell).lower()
            flag, start_, end_ = contains2(re_.sub('', cell), "".join(one_data["question_tok"]).lower())
            print(flag)
            print(start_)
            print(end_)
            if flag == True:
                final_header[iiii] = 2

    one_final["header_knowledge"] = final_header

    for row in one_table["rows"]:
        print(row)
        for cell in row:
            print(cell)
            cell = str(cell).lower()
            # cell = cell.replace('"',"")
            cell_tokens = tokenizer.tokenize(cell)
            print(cell_tokens)

            if len(cell_tokens)==0:
                continue

            flag, start_, end_ = contains2(re_.sub('', cell),  "".join(one_data["question_tok"]).lower())
            print(flag)
            print(start_)
            print(end_)
            # flag, start, end = contains(cell_tokens, nlu_tt1)
            # if flag==False:
            #     flag, start, end = contains(cell_tokens, nlu_tt2)
            #     if len(nlu_tt1) != len(nlu_tt2):
            #         continue
            if flag == True:
                try:
                    start = t_to_tt_idx1[charindex2wordindex[start_]]
                    end = t_to_tt_idx1[charindex2wordindex[end_]]
                    print(start)
                    print(end)
                    for ii in range(start,end):
                        final_question[ii] = 2
                    final_question[start] = 1
                    final_question[end] = 3
                    one_final["bertindex_knowledge"] = final_question
                    break
                except:
                    print("!!!")
                    continue
    if i%1000==0:
        print(i)
    if "bertindex_knowledge" not in one_final and len(one_final["sql"]["conds"])>0:
        print(one_data["question"])
        print(one_table["rows"])
        one_final["bertindex_knowledge"] = [0] * len(nlu_tt1)
        badcase+=1
    final_all.append(one_final)
  print(badcase)
  print(final_all)
  f = open(output_name,mode="w",encoding="utf-8")
  import json
  for line in final_all:
    json.dump(line, f)
    f.write('\n')
  f.close()
if __name__ == '__main__':
    process(ctable_data,ctable_table,"./data_and_model/ctable_knowledge.jsonl")
#process(dev_data,dev_table,"dev_knowledge.jsonl")



