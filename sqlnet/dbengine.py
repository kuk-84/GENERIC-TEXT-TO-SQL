# From original SQLNet code.
# Wonseok modified. 20180607

import records
import re
from babel.numbers import parse_decimal, NumberFormatError
import sqlite3

schema_re = re.compile(r'\((.+)\)') # group (.......) dfdf (.... )group
num_re = re.compile(r'[-+]?\d*\.\d+|\d+') # ? zero or one time appear of preceding character, * zero or several time appear of preceding character.
# Catch something like -34.34, .4543,
# | is 'or'

agg_ops = ['', 'MAX', 'MIN', 'COUNT', 'SUM', 'AVG']
cond_ops = ['=', '>', '<', 'OP']

class DBEngine:
    try:
        import sqlite3
        print("SQLite module is available.")
    except ImportError:
        print("SQLite module is not available.")
    
    print("inside creation")

    def __init__(self, fdb):
        #fdb = 'data/test.db'
        self.conn = sqlite3.connect(fdb)
        #self.db = records.Database(f'sqlite:///{fdb}').get_connection()
        print("connection")
        print(fdb)
        print("done")
    
        
    
    # def show_all_tables(self):
    #     query_result = self.db.query("SELECT name FROM sqlite_master WHERE type='table'")
    #     print("Tables in the database:")
    #     print(query_result)
    def show_all_tables(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print("Tables in the database:")
        for table in tables:
            print(table[0])
    

    # def execute_query(self, table_id, query, *args, **kwargs):
    #     return self.execute(table_id, query.sel_index, query.agg_index, query.conditions, *args, **kwargs)
    def execute_query(self, table_id, query, *args, **kwargs):
        return self.execute(table_id, query.sel_index, query.agg_index, query.conditions, *args, **kwargs)
    
    # def execute(self, table_id, select_index, aggregation_index, conditions, lower=True):
    #     if not table_id.startswith('table'):
    #         table_id = 'table_{}'.format(table_id.replace('-', '_'))
    #     #table_id=table_1_10015132_16
    #     table_info = self.db.query('SELECT sql from sqlite_master WHERE tbl_name = :name', name=table_id).all()[0].sql.replace('\n','')
    #     schema_str = schema_re.findall(table_info)[0]
    #     schema = {}
    #     for tup in schema_str.split(', '):
    #         c, t = tup.split()
    #         schema[c] = t
    #     select = 'col{}'.format(select_index)
    #     agg = agg_ops[aggregation_index]
    #     if agg:
    #         select = '{}({})'.format(agg, select)
    #     where_clause = []
    #     where_map = {}
    #     for col_index, op, val in conditions:
    #         if lower and (isinstance(val, str) or isinstance(val, str)):
    #             val = val.lower()
    #         if schema['col{}'.format(col_index)] == 'real' and not isinstance(val, (int, float)):
    #             try:
    #                 # print('!!!!!!value of val is: ', val, 'type is: ', type(val))
    #                 # val = float(parse_decimal(val)) # somehow it generates error.
    #                 val = float(parse_decimal(val, locale='en_US'))
    #                 # print('!!!!!!After: val', val)

    #             except NumberFormatError as e:
    #                 try:
    #                     val = float(num_re.findall(val)[0]) # need to understand and debug this part.
    #                 except:
    #                     # Although column is of number, selected one is not number. Do nothing in this case.
    #                     pass
    #         where_clause.append('col{} {} :col{}'.format(col_index, cond_ops[op], col_index))
    #         where_map['col{}'.format(col_index)] = val
    #     where_str = ''
    #     if where_clause:
    #         where_str = 'WHERE ' + ' AND '.join(where_clause)
    #     query = 'SELECT {} AS result FROM {} {}'.format(select, table_id, where_str)
    #     #print query
    #     out = self.db.query(query, **where_map)
    def execute(self, table_id, select_index, aggregation_index, conditions, lower=True):
        if not table_id.startswith('table'):
            table_id = f"table_{table_id.replace('-', '_')}"
        cursor = self.conn.cursor()
        cursor.execute('SELECT sql from sqlite_master WHERE tbl_name = ?', (table_id,))
        table_info = cursor.fetchone()[0]

        schema_str = table_info.split('(')[1].split(')')[0]
        schema = {}
        for tup in schema_str.split(', '):
            c, t = tup.split()
            schema[c] = t

        select = f'col{select_index}'
        agg = agg_ops[aggregation_index]
        if agg:
            select = f'{agg}({select})'

        where_clause = []
        where_values = []
        for col_index, op, val in conditions:
            if lower and isinstance(val, str):
                val = val.lower()
            if schema[f'col{col_index}'] == 'real' and not isinstance(val, (int, float)):
                try:
                    val = float(val)
                except ValueError:
                    val = None  # Replace with appropriate handling
            where_clause.append(f'col{col_index} {cond_ops[op]} ?')
            where_values.append(val)

        where_str = ''
        if where_clause:
            where_str = 'WHERE ' + ' AND '.join(where_clause)

        print("Constructed WHERE clause:", where_str)
        print("WHERE values:", where_values)

        query = f'SELECT {select} AS result FROM {table_id} {where_str}'
        print("Constructed SQL query:", query)

        cursor.execute(query, where_values)
        out = cursor.fetchall()
        print(out)

        return [o[0] for o in out]

        # return [o.result for o in out]
    
    # def execute_return_query(self, table_id, select_index, aggregation_index, conditions, lower=True):
    #     if not table_id.startswith('table'):
    #         table_id = 'table_{}'.format(table_id.replace('-', '_'))
    #     table_info = self.db.query('SELECT sql from sqlite_master WHERE tbl_name = :name', name=table_id).all()[0].sql.replace('\n','')
    #     schema_str = schema_re.findall(table_info)[0]
    #     schema = {}
    #     for tup in schema_str.split(', '):
    #         c, t = tup.split()
    #         schema[c] = t
    #     select = 'col{}'.format(select_index)
    #     agg = agg_ops[aggregation_index]
    #     if agg:
    #         select = '{}({})'.format(agg, select)
    #     where_clause = []
    #     where_map = {}
    #     for col_index, op, val in conditions:
    #         if lower and (isinstance(val, str) or isinstance(val, str)):
    #             val = val.lower()
    #         if schema['col{}'.format(col_index)] == 'real' and not isinstance(val, (int, float)):
    #             try:
    #                 # print('!!!!!!value of val is: ', val, 'type is: ', type(val))
    #                 # val = float(parse_decimal(val)) # somehow it generates error.
    #                 val = float(parse_decimal(val, locale='en_US'))
    #                 # print('!!!!!!After: val', val)

    #             except NumberFormatError as e:
    #                 val = float(num_re.findall(val)[0])
    #         where_clause.append('col{} {} :col{}'.format(col_index, cond_ops[op], col_index))
    #         where_map['col{}'.format(col_index)] = val
    #     where_str = ''
    #     if where_clause:
    #         where_str = 'WHERE ' + ' AND '.join(where_clause)
    #     query = 'SELECT {} AS result FROM {} {}'.format(select, table_id, where_str)
    #     #print query
    #     out = self.db.query(query, **where_map)


    #     return [o.result for o in out], query
    def execute_return_query(self, table_id, select_index, aggregation_index, conditions, lower=True):
        if not table_id.startswith('table'):
            table_id = 'table_{}'.format(table_id.replace('-', '_'))
            
        cursor = self.conn.cursor()
        cursor.execute('SELECT sql from sqlite_master WHERE tbl_name = ?', (table_id,))
        table_info = cursor.fetchone()[0]
        
        schema_str = table_info.split('(')[1].split(')')[0]
        schema = {}
        for tup in schema_str.split(', '):
            c, t = tup.split()
            schema[c] = t
        
        select = 'col{}'.format(select_index)
        agg = agg_ops[aggregation_index]
        if agg:
            select = '{}({})'.format(agg, select)
        
        where_clause = []
        where_values = []
        for col_index, op, val in conditions:
            if lower and isinstance(val, str):
                val = val.lower()
            if schema['col{}'.format(col_index)] == 'real' and not isinstance(val, (int, float)):
                try:
                    val = float(val)
                except ValueError:
                    val = NULL
            where_clause.append('col{} {}'.format(col_index, cond_ops[op]))
            where_values.append(val)
        
        where_str = ''
        if where_clause:
            where_str = 'WHERE ' + ' AND '.join(where_clause)
        
        
        query = 'SELECT {} AS result FROM {} {}'.format(select, table_id, where_str)
        print(query)
        cursor.execute(query, where_values)
        out = cursor.fetchall()

        return [o[0] for o in out], query

    
    # def show_table(self, table_id):
    #     if not table_id.startswith('table'):
    #         table_id = 'table_{}'.format(table_id.replace('-', '_'))
    #     rows = self.db.query('select * from ' +table_id)
    #     print(rows.dataset)
    def show_table(self, table_id):
        if not table_id.startswith('table'):
            table_id = 'table_{}'.format(table_id.replace('-', '_'))
        
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM {}'.format(table_id))
        rows = cursor.fetchall()
        
        for row in rows:
            print(row)

   
