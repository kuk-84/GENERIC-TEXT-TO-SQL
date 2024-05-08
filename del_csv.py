import sqlite3

def delete_table(connection, table_name):
    cursor = connection.cursor()
    cursor.execute("DROP TABLE IF EXISTS %s;" % table_name)
    print("Dropped table:", table_name)
    connection.commit()
    cursor.close()

# Example usage
db_path = './data_and_model/ctable.db'
table_to_delete = 'table_ftable4'  # Specify the table you want to delete
conn = sqlite3.connect(db_path)
delete_table(conn, table_to_delete)
conn.close()
