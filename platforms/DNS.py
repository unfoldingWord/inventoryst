from .Platform import Platform
import requests
import xmltodict
from pprint import pprint

class DNS(Platform):
    def __init__(self):
        super().__init__()

        # Namecheap
        self.namecheap_api_key = self._get_env('NAMECHEAP_API_KEY')
        self.namecheap_api_user = self._get_env('NAMECHEAP_API_USER')

        # Epik
        self.epik_api_key = self._get_env('EPIK_API_KEY')
        self.epik_api_url = f"https://usersapiv2.epik.com/v2/domains?SIGNATURE={self.epik_api_key}&per_page=100"

    def __get_json_from_xml(self, url):
        raw = requests.get(url)
        results = xmltodict.parse(raw.content)

        return results

    def __get_namecheap_data(self, command, query_params=None):
        query_params = f"&{query_params}" if query_params else ""

        namecheap_api_url = (f"https://api.namecheap.com/xml.response?ApiUser=dsmedia&"
                             f"ApiKey={self.namecheap_api_key}&UserName={self.namecheap_api_user}&"
                             f"Command=namecheap.{command}&ClientIp=77.160.30.156&PageSize=100&"
                             f"SortBy=NAME{query_params}")

        dict_results = self.__get_json_from_xml(namecheap_api_url)

        return dict_results

    def __enumerate_domains(self):
        dict_return = dict()
        dict_return["meta"] = dict()
        dict_return["content"] = dict()

        lst_domains = list()

        # NameCheap
        dict_domains = self.__get_namecheap_data("domains.getlist")

        domains = dict_domains["ApiResponse"]["CommandResponse"]["DomainGetListResult"]["Domain"]

        for item in domains:
            domain_parked = False
            domain_forwarded = False

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
                domain['nameservers'] = domain_dns["ApiResponse"]["CommandResponse"]["DomainDNSGetListResult"]["Nameserver"]

            # get configured hosts
            domain_hosts = self.__get_namecheap_data(command="domains.dns.gethosts", query_params=f"SLD={sld}&TLD={tld}")

            domain['hosts'] = list()
            if domain_hosts["ApiResponse"]["@Status"] == 'OK':
                for host in domain_hosts["ApiResponse"]["CommandResponse"]["DomainDNSGetHostsResult"]["host"]:
                    dict_host = dict()
                    dict_host["host"] = host["@Name"]
                    dict_host["type"] = host["@Type"]
                    dict_host["target"] = host["@Address"]
                    dict_host["ttl"] = host["@TTL"]

                    if host["@Address"] == 'parkingpage.namecheap.com.':
                        domain_parked = True
                    elif host["@Name"] == 'www' and host["@Type"] == "URL" and host["@Address"].find("http") > 0:
                        domain_forwarded = True

                    domain['hosts'].append(dict_host)

            # Determine domain status
            domain['status'] = "active"
            if len(domain['hosts']) == 0:
                domain['status'] = 'undeveloped'
            elif domain_parked is True:
                domain['status'] = "parked"
            elif domain_forwarded is True:
                domain['status'] = "forwarded"

            # Finally, add to lst_domains
            lst_domains.append(domain)

        # Epik
        #lst_domains = self._get_json_from_url(self.epik_api_url)['data']

        #print(len(lst_domains))
        #for item in lst_domains:
        #    print(item["domain"].lower())

        dict_return["meta"]["domain_count"] = len(lst_domains)
        dict_return["content"] = lst_domains

        return dict_return

    def __domains_to_markdown(self, inventory):
        lst_content = list()

        lst_content.append(">[!info] General information")
        lst_content.append(f">**Epik:** https://registrar.epik.com/domain/portfolio")
        lst_content.append(f">**Namecheap:** https://ap.www.namecheap.com/domains/list/")
        lst_content.append("**Number of domains:** " + str(inventory["meta"]["domain_count"]))
        lst_content.append("")

        # Sort alphabetically on the name
        domains_sorted = sorted(inventory["content"], key=lambda item: item["name"])

        for domain in domains_sorted:
            lst_content.append(f"### {domain['name']}")

        file = "dns.md"
        return {file: lst_content}


    def _build_content(self):
        md_main = dict()

        # domains
        inventory = self.__enumerate_domains()
        md_main.update(self.__domains_to_markdown(inventory))

        return md_main

