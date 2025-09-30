from .Platform import Platform
import mysql.connector
from pprint import pp
import re
from collections import OrderedDict


class MySQL(Platform):
    def __init__(self):
        super().__init__()

        self.__config = self.load_config('mysql')

        self.db = mysql.connector.connect(
            host=self.__config['host'],
            user=self.__config['user'],
            password=self.__config['password'],
            ssl_ca=self.__config['ssl_ca_file'],
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

        regex_grant_permissions = r"GRANT ([`%@A-Za-z0-9_,\s\(\)]+?)\s(ON|TO)"
        regex_grant_on = r"ON ([`\*\.a-z0-9-_]+)"
        regex_grant_options = r"(WITH GRANT OPTION)"

        with self.db.cursor() as cursor:
            cursor.execute(query_grants)

            grants = cursor.fetchall()
            for grant in grants:
                self._logger.debug(f'Grant: {str(grant)}')

                grant_permissions = re.findall(regex_grant_permissions, grant[0])
                grant_on = re.findall(regex_grant_on, grant[0])
                grant_options = re.findall(regex_grant_options, grant[0])
                self._logger.debug(f'Permissions: {str(grant_permissions)}')
                self._logger.debug(f'On: {str(grant_on)}')
                self._logger.debug(f'Options: {str(grant_options)}')
                lst_permissions.append({
                    "permissions": grant_permissions[0][0],
                    "target": grant_on[0].replace('`', '') if len(grant_on) > 0 else '',
                    "options": grant_options[0].replace('`', '') if len(grant_options) > 0 else '',
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

    def __markdown_users(self, dict_users):
        lst_content = list()

        lst_content.append(">[!info] General information")
        lst_content.append(self._item('Number of users', len(dict_users)))
        lst_content.append("")

        for user in dict_users:
            lst_content.append("")
            lst_content.append(self._header(f'`{user}`', 3))
            lst_content.append("| Table | Permissions | Options |")
            lst_content.append("| --- | --- | --- |")
            for permit in dict_users[user]:
                options = ""
                if permit['options']:
                    options = f"`{permit['options']}`"

                lst_content.append(f"| `{permit['target']}` | `{permit['permissions']}` | {options} |")

        file = "mysql/users.md"
        return {file: lst_content}

    def __markdown_databases(self, dict_databases):
        lst_content = list()

        lst_content.append(">[!info] General information")
        lst_content.append(self._item('Number of databases', len(dict_databases)))
        lst_content.append("")

        for db in dict_databases:
            lst_content.append(self._header(f"{db} ({len(dict_databases[db])} tables)", 3))

            for table in dict_databases[db]:
                lst_content.append(f"- `{table}`")

            lst_content.append("")

        file = "mysql/databases.md"
        return {file: lst_content}

    def _build_content(self):
        md_main = dict()

        user_inventory = self.__list_users()
        md_main.update(self.__markdown_users(user_inventory))

        db_inventory = self.__list_databases()
        md_main.update(self.__markdown_databases(db_inventory))

        return md_main
