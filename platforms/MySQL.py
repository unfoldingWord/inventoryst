from .Platform import Platform
import mysql.connector
from pprint import pprint


class MySQL(Platform):
    def __init__(self):
        super().__init__()

        self.db = mysql.connector.connect(
            host=self._get_env('MYSQL_HOST'),
            user=self._get_env('MYSQL_USER'),
            password=self._get_env('MYSQL_PASSWORD'),
            ssl_ca=self._get_env('MYSQL_SSL_CA_FILE'),
            ssl_verify_cert=True
        )

    def __list_users(self):
        query_users = "SELECT user,host FROM mysql.user;"

        query = "SHOW STATUS LIKE 'Ssl_cipher';"
        with self.db.cursor() as cursor:
            cursor.execute(query)

            for item in cursor:
                print(item)

    def __list_databases(self):
        db_ignore = ['information_schema', 'performance_schema', 'mysql', 'sys']

        dict_databases = dict()

        show_db_query = "SHOW DATABASES"
        with self.db.cursor() as cursor:
            cursor.execute(show_db_query)
            for db in cursor.fetchall():
                if db[0] not in db_ignore:
                    dict_databases[db[0]] = self.__list_tables(db[0])

            return dict_databases

    def __list_tables(self, database):
        lst_tables = list()

        show_db_query = f"SHOW TABLES FROM `{database}`"
        with self.db.cursor() as cursor:
            cursor.execute(show_db_query)
            for table in cursor.fetchall():
                lst_tables.append(table[0])

            return lst_tables

    def __users_to_markdown(self, dict_users):
        lst_content = list()

        lst_content.append(">[!info] General information")
        lst_content.append("**Number of users:** " + str(len(dict_users)))
        lst_content.append("")

        file = "mysql/users.md"
        return {file: lst_content}

    def __databases_to_markdown(self, dict_databases):
        lst_content = list()

        lst_content.append(">[!info] General information")
        lst_content.append("**Number of databases:** " + str(len(dict_databases)))
        lst_content.append("")

        for db in dict_databases:
            lst_content.append(f"### {db} ({len(dict_databases[db])} tables)")

            for table in dict_databases[db]:
                lst_content.append(f"- `{table}`")

            lst_content.append("")

        file = "mysql/databases.md"
        return {file: lst_content}

    def _build_content(self):
        md_main = dict()

        # user_inventory = self.__list_users()
        # md_main.update(self.__users_to_markdown(user_inventory))

        db_inventory = self.__list_databases()
        md_main.update(self.__databases_to_markdown(db_inventory))


        #exit()

        return md_main
