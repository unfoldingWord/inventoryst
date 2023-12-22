from .Platform import Platform
import mysql.connector
from pprint import pprint
import re
from collections import OrderedDict


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
        dict_users = dict()

        query_users = "SELECT `user`, `host` FROM `mysql`.`user`"

        with self.db.cursor() as cursor:
            cursor.execute(query_users)

            users = cursor.fetchall()
            for user in users:
                lst_grants = self.__list_grants(user[0], user[1])

                dict_users[user[0] + "@" + user[1]] = lst_grants

        dict_users = OrderedDict(sorted(dict_users.items()))
        return dict_users

    def __list_grants(self, user, host):
        lst_permissions = list()

        query_grants = f"SHOW GRANTS FOR '{user}'@'{host}'"
        self._logger.debug(query_grants)

        regex_grant = r"GRANT ([A-Za-z0-9_,\s\(\)]+) ON ([\*`\.a-z0-9-_]+) TO ['a-z@%.]+\s*(WITH GRANT OPTION)?"

        with self.db.cursor() as cursor:
            cursor.execute(query_grants)

            grants = cursor.fetchall()
            for grant in grants:
                self._logger.debug(grant)
                permissions = re.findall(regex_grant, grant[0])[0]
                self._logger.debug(permissions)
                lst_permissions.append({
                    "permissions": permissions[0],
                    "target": permissions[1].replace('`', ''),
                    "options": permissions[2]
                })

        lst_permissions_sorted = sorted(lst_permissions, key=lambda item: item["target"])
        return lst_permissions_sorted

    def __list_databases(self):
        db_ignore = ['information_schema', 'performance_schema', 'mysql', 'sys']

        dict_databases = dict()

        show_db_query = "SHOW DATABASES"
        with self.db.cursor() as cursor:
            cursor.execute(show_db_query)

            dbs = cursor.fetchall()
            for db in dbs:
                if db[0] not in db_ignore:
                    dict_databases[db[0]] = self.__list_tables(db[0])

            return dict_databases

    def __list_tables(self, database):
        lst_tables = list()

        show_db_query = f"SHOW TABLES FROM `{database}`"
        with self.db.cursor() as cursor:
            cursor.execute(show_db_query)

            tables = cursor.fetchall()
            for table in tables:
                lst_tables.append(table[0])

            return lst_tables

    def __users_to_markdown(self, dict_users):
        lst_content = list()

        lst_content.append(">[!info] General information")
        lst_content.append("**Number of users:** " + str(len(dict_users)))
        lst_content.append("")

        for user in dict_users:
            lst_content.append("")
            lst_content.append(f"### `{user}`")
            lst_content.append("| Table | Permissions | Options |")
            lst_content.append("| --- | --- | --- |")
            for permit in dict_users[user]:
                options = ""
                if permit['options']:
                    options = f"`{permit['options']}`"

                lst_content.append(f"| `{permit['target']}` | `{permit['permissions']}` | {options} |")

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

        user_inventory = self.__list_users()
        md_main.update(self.__users_to_markdown(user_inventory))

        db_inventory = self.__list_databases()
        md_main.update(self.__databases_to_markdown(db_inventory))

        return md_main
