from .Platform import Platform
import requests
import xmltodict
from pprint import pprint
import datetime
import time


class DNS(Platform):
    def __init__(self):
        super().__init__()

        # Page alias
        self._add_page_property('aliases', ['Domain List'])

        # Namecheap
        self.namecheap_api_key = self._get_env('NAMECHEAP_API_KEY')
        self.namecheap_api_user = self._get_env('NAMECHEAP_API_USER')
        self.__namecheap_api_counter = 0

        # Epik
        self.epik_api_key = self._get_env('EPIK_API_KEY')

    def __get_json_from_xml(self, url):
        raw = requests.get(url)
        results = xmltodict.parse(raw.content)

        return results

    def __get_epik_data(self, command):
        # https://docs.userapi.epik.com/v2/

        epik_api_url = f"https://usersapiv2.epik.com/v2/{command}?SIGNATURE={self.epik_api_key}&per_page=100"

        dict_results = self._get_json_from_url(epik_api_url)

        self._logger.debug(dict_results)

        return dict_results

    def __get_namecheap_data(self, command, query_params=None):
        query_params = f"&{query_params}" if query_params else ""

        namecheap_api_url = (f"https://api.namecheap.com/xml.response?ApiUser=dsmedia&"
                             f"ApiKey={self.namecheap_api_key}&UserName={self.namecheap_api_user}&"
                             f"Command=namecheap.{command}&ClientIp=77.160.30.156&PageSize=100&"
                             f"SortBy=NAME{query_params}")

        self._logger.debug(namecheap_api_url)

        dict_results = self.__get_json_from_xml(namecheap_api_url)

        #self._logger.debug(dict_results)

        # If we hit the API rate limit (50/min, 700/hour, and 8000/day across the whole key), wait 1 minute, then retry
        # https://www.namecheap.com/support/knowledgebase/article.aspx/9739/63/api-faq/#z
        while (dict_results["ApiResponse"]["@Status"] == "ERROR" and
               dict_results["ApiResponse"]["Errors"]["Error"]["#text"] == 'Too many requests'):
            self._logger.info(f"Namecheap API rate limit hit ({self.__namecheap_api_counter} calls). "
                              f"Waiting (1m) and retrying...")

            time.sleep(60)
            dict_results = self.__get_json_from_xml(namecheap_api_url)

        # indicates succesful call
        self.__namecheap_api_counter += 1

        return dict_results

    def __enumerate_namecheap_domains(self):
        lst_domains = list()

        # NameCheap
        dict_domains = self.__get_namecheap_data("domains.getlist")

        domains = dict_domains["ApiResponse"]["CommandResponse"]["DomainGetListResult"]["Domain"]
        self._logger.info(f"Number of domains: {len(domains)}")

        # Just 5 domains is enough for local debugging
        if self._get_env('STAGE') == 'dev':
            domains = domains[0:5]

        for item in domains:
            self._logger.info(f"Collecting info for '{item['@Name']}'")

            domain = dict()
            domain['name'] = item["@Name"]
            domain['registrar'] = 'Namecheap'
            domain['registration_date'] = item["@Created"]
            domain['expiration_date'] = item["@Expires"]
            domain['auto_renew'] = True if item["@AutoRenew"] == 'true' else False

            # Process domain
            sld, tld = domain['name'].split(".")

            # get DNS servers
            domain_dns = self.__get_namecheap_data(command="domains.dns.getlist", query_params=f"SLD={sld}&TLD={tld}")
            if domain_dns["ApiResponse"]["@Status"] == 'OK':
                domain['nameservers'] = domain_dns["ApiResponse"]["CommandResponse"]["DomainDNSGetListResult"][
                    "Nameserver"]

            # get configured hosts
            domain_hosts = self.__get_namecheap_data(command="domains.dns.gethosts",
                                                     query_params=f"SLD={sld}&TLD={tld}")

            domain['hosts'] = list()
            domain['custom_dns'] = False
            domain_parked = False
            if domain_hosts["ApiResponse"]["@Status"] == 'OK':
                if 'host' in domain_hosts["ApiResponse"]["CommandResponse"]["DomainDNSGetHostsResult"]:
                    for host in domain_hosts["ApiResponse"]["CommandResponse"]["DomainDNSGetHostsResult"]["host"]:
                        # Sometimes the API gives weird data back...
                        if not type(host) is dict:
                            str_host = str(host)
                            self._logger.warning(
                                f"Unexpected value for host in domain '{domain['name']}': {str_host} ({type(host)})")
                            continue

                        dict_host = dict()
                        dict_host["host"] = host["@Name"]
                        dict_host["type"] = host["@Type"]
                        dict_host["target"] = host["@Address"]
                        dict_host["ttl"] = host["@TTL"]

                        if host["@Address"] == 'parkingpage.namecheap.com.':
                            domain_parked = True

                        domain['hosts'].append(dict_host)
            elif domain_hosts["ApiResponse"]["CommandResponse"]["DomainDNSGetHostsResult"]["@IsUsingOurDNS"] == 'false':
                # I could do fancy pancy here, with pulling hosts from other platforms (AWS?)
                # But for now, just keep it simple
                domain['custom_dns'] = True
            else:
                str_error = str(domain_hosts)
                self._logger.warning(f"Unexpected host data returned for domain '{domain['name']}': {str_error}")

            # Determine domain status
            domain['status'] = "active"
            if 'hosts' in domain and len(domain['hosts']) == 0:
                if domain['custom_dns'] is False:
                    domain['status'] = 'undeveloped'
            elif domain_parked is True:
                domain['status'] = "parked"

            # Finally, add to lst_domains
            lst_domains.append(domain)

        return lst_domains

    def __enumerate_epik_domains(self):
        lst_domains = list()

        domains = self.__get_epik_data('domains')['data']
        self._logger.info(f"Number of domains: {len(domains)}")

        # Just 5 domains is enough for local debugging
        if self._get_env('STAGE') == 'dev':
            domains = domains[0:5]

        for item in domains:
            self._logger.info(f"Collecting info for '{item['domain'].lower()}'")

            domain = dict()
            domain["name"] = item["domain"].lower()
            domain["registrar"] = "Epik"
            domain["registration_date"] = datetime.datetime.strptime(item["registration_date"],
                                                                     '%Y-%m-%d').strftime('%m/%d/%Y')
            domain["expiration_date"] = datetime.datetime.strptime(item["expiration_date"],
                                                                   '%Y-%m-%d').strftime('%m/%d/%Y')
            domain["auto_renew"] = item["auto_renew"]
            domain["nameservers"] = item["name_servers"]

            # Other DNS host
            domain['custom_dns'] = False
            ns_epik = len([server for server in domain['nameservers'] if not server.lower().find('epik.com') == -1])
            if bool(ns_epik) is False:
                domain['custom_dns'] = True

            # Get the hosts
            domain['hosts'] = list()
            domain_parked = False

            hosts = self.__get_epik_data(f"domains/{item['domain']}/records")['data']['records']
            for host in hosts:
                dict_host = dict()
                dict_host['host'] = host['name']
                dict_host['type'] = host['type']
                dict_host['target'] = host['data']
                dict_host['ttl'] = host['ttl']

                if host['type'] == 'A' and host['data'] == '185.83.214.222':
                    domain_parked = True

                domain['hosts'].append(dict_host)

            # Determine domain status
            domain['status'] = "active"
            if 'hosts' in domain and len(domain['hosts']) == 0:
                if domain['custom_dns'] is False:
                    domain['status'] = 'undeveloped'
            elif domain_parked is True:
                domain['status'] = "parked"

            # Finally, add to lst_domains
            lst_domains.append(domain)

        return lst_domains

    def __enumerate_domains(self):
        dict_return = dict()
        dict_return["meta"] = dict()
        dict_return["content"] = dict()

        lst_domains = list()

        self._logger.info("Getting domain info from Namecheap")
        lst_namecheap_domains = self.__enumerate_namecheap_domains()
        lst_domains += lst_namecheap_domains

        # Epik
        self._logger.info("Getting domain info from Epik")
        lst_epik_domains = self.__enumerate_epik_domains()
        lst_domains += lst_epik_domains

        dict_return["meta"]["domain_count"] = len(lst_domains)
        dict_return["content"] = lst_domains

        return dict_return

    def __domains_to_markdown(self, inventory):
        lst_content = list()

        # Stats for Namecheap
        domains_nc = [domain for domain in inventory['content'] if domain['registrar'] == 'Namecheap']
        parked_domains_nc = len([domain for domain in domains_nc if domain['status'] == 'parked'])
        active_domains_nc = len([domain for domain in domains_nc if domain['status'] == 'active'])
        undeveloped_domains_nc = len([domain for domain in domains_nc if domain['status'] == 'undeveloped'])

        # Stats for Epik
        domains_epik = [domain for domain in inventory['content'] if domain['registrar'] == 'Epik']
        parked_domains_epik = len([domain for domain in domains_epik if domain['status'] == 'parked'])
        active_domains_epik = len([domain for domain in domains_epik if domain['status'] == 'active'])
        undeveloped_domains_epik = len([domain for domain in domains_epik if domain['status'] == 'undeveloped'])

        lst_content.append(">[!info] General information")
        lst_content.append(f">**Number of domains:** {inventory['meta']['domain_count']}")
        lst_content.append(f">**[Epik domains](https://registrar.epik.com/domain/portfolio):** {len(domains_epik)}")
        lst_content.append(f">- **Active**: {active_domains_epik}")
        lst_content.append(f">- **Undeveloped**: {undeveloped_domains_epik}")
        lst_content.append(f">- **Parked**: {parked_domains_epik}")
        lst_content.append(">")
        lst_content.append(f">**[Namecheap domains](https://ap.www.namecheap.com/domains/list/):** {len(domains_nc)}")
        lst_content.append(f">- **Active**: {active_domains_nc}")
        lst_content.append(f">- **Undeveloped**: {undeveloped_domains_nc}")
        lst_content.append(f">- **Parked**: {parked_domains_nc}")
        lst_content.append("")

        # Sort alphabetically on the name
        domains_sorted = sorted(inventory["content"], key=lambda item: item["name"])

        for domain in domains_sorted:
            lst_content.append(f"### {domain['name']}")

            # Status
            status_color = ""
            match domain['status']:
                case 'active':
                    status_color = "green"
                case 'undeveloped':
                    status_color = "grey"
                case 'parked':
                    status_color = "blue"

            str_status = f"<span style=\"font-weight: bold; color: {status_color}\">[ {domain['status']} ]</span>"
            lst_content.append(f"**Status:** {str_status}")

            lst_content.append(f"**Registrar:** {domain['registrar']}")

            # Registration date
            reg_date = datetime.datetime.strptime(domain['registration_date'], "%m/%d/%Y").strftime("%a, %b %-d, %Y")
            lst_content.append(f"**Registration date:** {reg_date}")

            # Expiry date
            exp_date = datetime.datetime.strptime(domain['expiration_date'], "%m/%d/%Y")
            date_diff = exp_date - datetime.datetime.now()
            exp_date_color = "red" if date_diff.days <= 7 else ""
            str_exp_date = exp_date.strftime("%a, %b %-d, %Y")
            lst_content.append(f"**Expiration date:** <span style=\"color: {exp_date_color}\">{str_exp_date}</span>")

            # Auto-renew
            renew_color = 'green' if domain['auto_renew'] is True else 'red'
            renew_status = 'yes' if domain['auto_renew'] is True else 'no'
            str_renew = f"<span style=\"font-weight: bold; color: {renew_color}\">{renew_status}</span>"
            lst_content.append(f"**Auto renew:** {str_renew}")

            # Nameservers
            if 'nameservers' in domain:
                ns = "`" + "`,`".join(domain['nameservers']) + "`"
                lst_content.append(f"**Nameservers:** {ns}")

            # Hosts
            if 'hosts' in domain and len(domain['hosts']) > 0:
                lst_content.append(f"**Hosts:** {len(domain['hosts'])}")
                lst_content.append("")
                lst_content.append("| Host | Type | Target | TTL |")
                lst_content.append("| --- | --- | --- | --- |")
                for host in domain["hosts"]:
                    if type(host) is dict:
                        str_fields = (f" | `{host['host']}` | `{host['type']}` "
                                      f"| `{host['target']}` | {host['ttl']} |")
                        lst_content.append(str_fields)
            elif domain['custom_dns'] is True:
                lst_content.append(f"**Hosts:** _Defined outside {domain['registrar']}_")

            lst_content.append("")

        file = "dns.md"
        return {file: lst_content}

    def _build_content(self):
        md_main = dict()

        # domains
        inventory = self.__enumerate_domains()
        md_main.update(self.__domains_to_markdown(inventory))

        return md_main
