from .Platform import Platform
import requests
import xmltodict
from pprint import pprint
import datetime


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
                if 'host' in domain_hosts["ApiResponse"]["CommandResponse"]["DomainDNSGetHostsResult"]:
                    for host in domain_hosts["ApiResponse"]["CommandResponse"]["DomainDNSGetHostsResult"]["host"]:
                        dict_host = dict()
                        dict_host["host"] = host["@Name"]
                        dict_host["type"] = host["@Type"]
                        dict_host["target"] = host["@Address"]
                        dict_host["ttl"] = host["@TTL"]

                        if host["@Address"] == 'parkingpage.namecheap.com.':
                            domain_parked = True
                        elif host["@Name"] == 'www' and host["@Type"] == "URL" and host["@Address"].find("http") != -1:
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

        cnt = 0
        parked_domains = len([domain for domain in inventory['content'] if domain['status'] == 'parked'])
        active_domains = len([domain for domain in inventory['content'] if domain['status'] == 'active'])
        forwarded_domains = len([domain for domain in inventory['content'] if domain['status'] == 'forwarded'])
        undeveloped_domains = len([domain for domain in inventory['content'] if domain['status'] == 'undeveloped'])

        lst_content.append(">[!info] General information")
        lst_content.append(f">**Epik:** https://registrar.epik.com/domain/portfolio")
        lst_content.append(f">**Namecheap:** https://ap.www.namecheap.com/domains/list/")
        lst_content.append(">**Number of domains:** " + str(inventory["meta"]["domain_count"]))
        lst_content.append(f">- **Active**: {active_domains}")
        lst_content.append(f">- **Undeveloped**: {undeveloped_domains}")
        lst_content.append(f">- **Parked**: {parked_domains}")
        lst_content.append(f">- **Forwarded**: {forwarded_domains}")
        lst_content.append("")

        # Sort alphabetically on the name
        domains_sorted = sorted(inventory["content"], key=lambda item: item["name"])

        for domain in domains_sorted:
            lst_content.append(f"### {domain['name']}")

            # Status
            status_color = "black"
            match domain['status']:
                case 'active':
                    status_color = "green"
                case 'undeveloped':
                    status_color = "grey"
                case 'parked':
                    status_color = "blue"
                case 'forwarded':
                    status_color = "orange"

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
                lst_content.append("")
                lst_content.append("| Host | Type | Target | TTL |")
                lst_content.append("| --- | --- | --- | --- |")
                for host in domain["hosts"]:
                    lst_content.append(f" | {host['host']} | {host['type']} | {host['target']} | {host['ttl']} |")

            lst_content.append("")

            #pprint(domain)


        file = "dns.md"
        return {file: lst_content}


    def _build_content(self):
        md_main = dict()

        # domains
        inventory = self.__enumerate_domains()
        md_main.update(self.__domains_to_markdown(inventory))

        return md_main

