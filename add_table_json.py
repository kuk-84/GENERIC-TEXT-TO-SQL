
import argparse, csv, json
import pandas as pd
from sqlalchemy import Column, create_engine, Integer, MetaData, String, Table
from sqlalchemy.exc import ArgumentError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import create_session, mapper

def table_to_json(table_id, table_name, csv_file):
    df = pd.read_csv("./data_and_model/"+csv_file)
    record = {
        "header": list(df.columns),
        "types": ["real" if dt.kind == 'f' else "text" for dt in df.dtypes],
        "id": table_id,
        "rows": df.values.tolist(),
        "name": table_name
    }
    with open("./data_and_model/ctable_tok.tables.jsonl", 'w') as fout:
        json.dump(record, fout)
        #fout.write('\n')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('table_id')
    parser.add_argument('table_name')
    parser.add_argument('csv_file')
    args = parser.parse_args()
    table_to_json(args.table_id, args.table_name,args.csv_file)
