import os
import re
import time
import json
import ctypes
import subprocess

from bs4 import BeautifulSoup
from curl_cffi import requests
from urllib.parse import urlparse
from requests_html import HTMLSession

class OptionsLoader:
    @staticmethod
    def load_options(file_path="options.json"):
        with open(file_path, "r") as json_file:
            return json.load(json_file)

class FileDownloader:
    CHUNK_SIZE = 8192

    def __init__(self, options):
        self.session = HTMLSession()
        self.games_folder = options["games_folder"]
        self.updates_folder = options["updates_folder"]
        self.dlc_folder = options["dlc_folder"]

    def update_console_title(self, file_name, downloaded_size, total_size, start_time):
        percentage = (downloaded_size / total_size) * 100
        elapsed_time = time.time() - start_time
        download_speed = downloaded_size / elapsed_time if elapsed_time > 0 else 0
        remaining_size = total_size - downloaded_size
        eta_seconds = remaining_size / download_speed if download_speed > 0 else 0

        eta_formatted = time.strftime("%H:%M:%S", time.gmtime(eta_seconds))

        ctypes.windll.kernel32.SetConsoleTitleW(f"@hitting-them - Switch Rom Installer | {file_name} - {downloaded_size/1024/1024:.2f}MB / {total_size/1024/1024:.2f}MB - {percentage:.2f}% | ETA: {eta_formatted}")
    
    def download_file(self, url, file_name, game_title, headers):
        with self.session.get(url, headers=headers, stream=True) as response:
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            start_time = time.time()

            install_folder = os.path.join(self.games_folder, game_title)
            if "update" in file_name.lower():
                install_folder = os.path.join(self.updates_folder, game_title)
            elif "dlc" in file_name.lower():
                install_folder = os.path.join(self.dlc_folder, game_title)

            os.makedirs(install_folder, exist_ok=True)

            with open(os.path.join(install_folder, file_name), 'wb') as file:
                for chunk in response.iter_content(chunk_size=self.CHUNK_SIZE):
                    if chunk:
                        file.write(chunk)
                        downloaded_size += len(chunk)
                        self.update_console_title(file_name, downloaded_size, total_size, start_time)

class GOFile:
    def __init__(self, options):
        self.options = options

        self.session = HTMLSession()
        self.token = self.__get_token()
        
    def __get_token(self):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept": "*/*",
            "Connection": "keep-alive",
        }

        create_account_response = self.session.get("https://api.gofile.io/createAccount", headers=headers).json()
        api_token = create_account_response["data"]["token"]
        
        account_response = self.session.get("https://api.gofile.io/getAccountDetails?token=" + api_token, headers=headers).json()

        if account_response["status"] != 'ok':
            print("[!] Could not setup GOFile!")
            input()
            exit()

        return api_token
    
    def fetch_download(self, url):
        try:
            url_id = url.split("/")[-1]
            url = f"https://api.gofile.io/getContent?contentId={url_id}&token={self.token}&websiteToken=7fd94ds12fds4&cache=true"
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept": "*/*",
                "Connection": "keep-alive",
            }

            response = self.session.get(url, headers=headers).json()
            if response["status"] != 'ok':
                print("[!] GOFile might be down!")
                input()
                exit()
            
            data = response["data"]
            if "contents" in data.keys():
                contents = data["contents"]
                for content in contents.values():
                    if content["type"] == "file":
                        return content["link"], content["name"]
        except:
            time.sleep(2)
            self.fetch_download(url)
    
    def download_from_url(self, url, file_name, game_title):
        headers = {
            "Cookie": "accountToken=" + self.token,
            "Accept-Encoding": "gzip, deflate, br",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Referer": url + ("/" if not url.endswith("/") else ""),
            "Origin": url,
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache"
        }
        
        file_downloader = FileDownloader(self.options)
        file_downloader.download_file(url, file_name, game_title, headers)

class Fichier:
    def __init__(self, options):
        self.options = options

        self.session = HTMLSession()
    
    def __get_connected_interface(self):
        try:
            result = subprocess.run(['netsh', 'interface', 'show', 'interface'], capture_output=True, text=True)
            lines = result.stdout.splitlines()
            return next((line.split()[3] for line in lines if len(line.split()) == 4 and line.split()[1] == "Connected"), None)
        except subprocess.CalledProcessError as e:
            print(f"[!] Error fetching connected interface: {e}")
            exit()

    def __wait_until_connection(self):
        connected_interface = self.__get_connected_interface()
        if not connected_interface:
            time.sleep(3)
            self.__wait_until_connection()

    def apply_bypass(self):
        connection_interface = self.__get_connected_interface()
        subprocess.run(['netsh', 'interface', 'set', 'interface', connection_interface, 'admin=disable'], check=True, capture_output=True)
        subprocess.run(['netsh', 'interface', 'set', 'interface', connection_interface, 'admin=enable'], check=True, capture_output=True)
        self.__wait_until_connection()
    
    def fetch_download(self, link):
        try:
            response = self.session.get(link)
            soup = BeautifulSoup(response.content, 'html.parser')

            input_element = soup.find('input', {'type': 'hidden', 'name': 'adz'})
            file_name = soup.find_all('td', class_='normal')[1].text

            if input_element and file_name:
                adz = input_element['value']
                final_response = self.session.post(link, data={"adz": adz})
                anchor_element = BeautifulSoup(final_response.content, 'html.parser').find('a', class_='ok btn-general btn-orange')

                if anchor_element:
                    return anchor_element['href'], file_name
        except Exception:
            print("[!] File is possibly removed from 1fichier")
            input()
            exit()
    
    def download_from_url(self, url, file_name, game_title):
        file_downloader = FileDownloader(self.options)
        file_downloader.download_file(url, file_name, game_title, {})

class Qiwi:
    BASE_URL = "https://qiwi.lol/"
    def __init__(self, options):
        self.options = options

        self.session = HTMLSession()
    
    def fetch_download(self, url):
        try:
            response = self.session.get(url)
            parser = BeautifulSoup(response.content, 'html.parser')

            file_name = parser.find("h1").text
            download_link = f"{self.BASE_URL}{os.path.splitext(url.split('/')[-1])[0]}.{os.path.splitext(file_name)[1][1:]}"

            return download_link, file_name
        except Exception:
            print("[!] File is possibly removed from Qiwi")
            input()
            exit()
    
    def download_from_url(self, url, file_name, game_title):
        file_downloader = FileDownloader(self.options)
        file_downloader.download_file(url, file_name, game_title, {})

class SwitchROM:
    BASE_URL = "https://nxbrew.com/"

    def __init__(self):
        self.session = HTMLSession()

    def set_console_title(self, title_suffix=""):
        os.system("cls")
        title = f"@hitting-them - Switch Rom Installer | {title_suffix}".strip()
        ctypes.windll.kernel32.SetConsoleTitleW(title)

    def search_game(self, query: str, page="1"):
        query_modified = query.replace(" ", "+")

        while True:
            search_url = f"{self.BASE_URL}page/{page}/?s={query_modified}"
            response = self.session.get(search_url)
            response.raise_for_status()

            parser = BeautifulSoup(response.content, "html.parser")

            page_element = parser.find("span", class_="pages")
            if page_element:
                last_page = page_element.get_text().split()[-1]
            else:
                last_page = page

            self.set_console_title(f"Search: {query} - Page: {page}/{last_page}")

            print("[-] Search Results:")
            games = parser.find_all("article", class_=lambda x: "page" not in x)
            for index, game in enumerate(games, start=1):
                thumbnail_element = game.find("div", class_="post-thumbnail")
                if thumbnail_element:
                    img_element = thumbnail_element.find("img")

                    game_name = img_element.get("alt", "").replace("-", " ").title()
                    print(f"[{index}] {game_name}")

            print("[0] Next Page")

            selected_index = int(input())
            if selected_index == 0:
                page = str(int(page) + 1)
            elif 1 <= selected_index <= len(games):
                selected_game_link = games[selected_index - 1].find("h2", class_="post-title").a.get("href")
                return selected_game_link
            else:
                print("[!] Invalid index selected.")

    def get_game_rom(self, game_link):
        try:
            response = self.session.get(game_link)
            response.raise_for_status()

            parser = BeautifulSoup(response.content, "html.parser")
            
            game_title = parser.find("strong", string="Title: ").next_sibling.strip()
            game_title = re.sub(r'[:*?<>|]', '', game_title)

            self.set_console_title(game_title)

            rom_elements = []
            multiple_regions = []

            for element in parser.find_all("p", class_=["has-text-align-center", "has-text-color", "has-background", "has-medium-font-size"]):
                strong = element.find("strong")
                if strong and "Region" in strong.get_text() and "[" in strong.get_text():
                    multiple_regions.append(element)

            if multiple_regions:
                print("[-] Select Region:")

                for index, region in enumerate(multiple_regions, start=1):
                    region_name = region.find("strong").get_text()
                    print(f"[{index}] {region_name}")

                selected_region_index = int(input())
                if 1 <= selected_region_index <= len(multiple_regions):
                    selected_region = multiple_regions[selected_region_index - 1]
                    game_id = re.search(r'\[([0-9A-Za-z]{12,})\]', selected_region.find("strong").get_text())

                    next_tag = selected_region.find_next_sibling()

                    while next_tag and next_tag.name != "p":
                        if next_tag.name == "div":
                            if next_tag.find_all():
                                rom_elements.append(next_tag)
                        next_tag = next_tag.find_next_sibling()
    
                else:
                    print("[!] Invalid region index selected.")
                    exit()
            else:
                game_id = parser.find("strong", string="Title ID: ").next_sibling.strip()
                
                for element in parser.find_all("p"):
                    _class = element.get("class", [])
                    if "has-background" and "has-very-light-gray-color" and "has-vivid-red-background-color" in _class:
                        if element.find("strong").get_text() == "Download Links":
                            download_title = element

                first_iteration = True
                next_tag = download_title.find_next_sibling()
                while next_tag:
                    if next_tag.name == "div":
                        if next_tag.find_all():
                            rom_elements.append(next_tag)

                    if next_tag.name == "p":
                        if first_iteration:
                            first_iteration = False
                        else:
                            break
                    
                    next_tag = next_tag.find_next_sibling()

            rom_options = []
            for rom_element in rom_elements:
                title_element = rom_element.find("p", class_="has-medium-font-size")
                if title_element:
                    title = title_element.find("strong").get_text()
                    rom_options.append(title)
            
            print("Select ROM options (seperated by commas):")
            for index, rom_option in enumerate(rom_options, start=1):
                print(f"[{index}] {rom_option}")

            selected_indices = [int(index) for index in input().split(",") if index.strip()]

            selected_rom_options = []
            for selected_index in selected_indices:
                if 1 <= selected_index <= len(rom_options):
                    selected_rom_option = rom_elements[selected_index - 1]
                    selected_rom_options.append(selected_rom_option)
                else:
                    print("[!] Invalid region index selected.")
                    exit()
            
            download_links = []
            for selected_option in selected_rom_options:
                selected_hoster = None
                hosters = []
                option_name = selected_option.find("p", class_="has-medium-font-size").find("strong").get_text()

                print(f"Select Hoster for {option_name}: ")
                if selected_option.find("strong", string="1Fichier") or selected_option.find("a", string="1Fichier"):
                    hosters.append("1Fichier")
                if selected_option.find("strong", string="GoFile") or selected_option.find("a", string="GoFile"):
                    hosters.append("GoFile")
                if selected_option.find("strong", string="Qiwi") or selected_option.find("a", string="Qiwi"):
                    hosters.append("Qiwi")
                
                for index, hoster in enumerate(hosters, start=1):
                    print(f"[{index}] {hoster}")
                
                hoster_input = int(input())
                if 1 <= hoster_input <= len(hosters):
                    selected_hoster = hosters[hoster_input - 1]

                download_element = selected_option.find("strong", string=selected_hoster)
                if download_element:
                    file_downloads = download_element.find_parent().find_all("a")
                    for download_link in file_downloads:
                        download_links.append(download_link["href"])
                else:
                    single_download_element = selected_option.find("a", string=selected_hoster)
                    download_links.append(single_download_element["href"])
        
            return game_title, game_id, download_links
        except Exception as e:
            print(f"[!] Error occurred: {e}")
    
    def recaptcha_v3_bypass(self):
        ANCHOR_URL = 'https://www.google.com/recaptcha/api2/anchor?ar=1&k=6Lcr1ncUAAAAAH3cghg6cOTPGARa8adOf-y9zv2x&co=aHR0cHM6Ly9vdW8ucHJlc3M6NDQz&hl=en&v=pCoGBhjs9s8EhFOHJFe8cqis&size=invisible&cb=ahgyd1gkfkhe'
        url_base = 'https://www.google.com/recaptcha/'
        post_data = "v={}&reason=q&c={}&k={}&co={}"
        matches = re.findall('([api2|enterprise]+)\/anchor\?(.*)', ANCHOR_URL)[0]
        url_base += matches[0]+'/'
        params = matches[1]
        request = self.session.get(url_base+'anchor', params=params, headers={'content-type': 'application/x-www-form-urlencoded'})
        token = re.findall(r'"recaptcha-token" value="(.*?)"', request.text)[0]
        params = dict(pair.split('=') for pair in params.split('&'))
        post_data = post_data.format(params["v"], token, params["k"], params["co"])
        request = self.session.post(url_base+'reload', params=f'k={params["k"]}', data=post_data, headers={'content-type': 'application/x-www-form-urlencoded'})
        answer = re.findall(r'"rresp","(.*?)"', request.text)[0]
        return answer
    
    def bypass_1link_club(self, url):
        request = self.session.get(url)
        request.html.render()

        parser = BeautifulSoup(request.content, "lxml")
        download_link = parser.find("a", {"id": "download"})

        redirect_url = download_link.get("href")
        request = self.session.get(redirect_url, allow_redirects=True)

        return request.url

    def bypass_ouo_io(self, url):
        temp_url = url.replace("ouo.press", "ouo.io")
        client = requests.Session()
        client.headers.update({
            'authority': 'ouo.io',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
            'cache-control': 'max-age=0',
            'referer': 'http://www.google.com/ig/adde?moduleurl=',
            'upgrade-insecure-requests': '1',
        })

        try:
            parsed = urlparse(temp_url)
            id = temp_url.split('/')[-1]
            request = client.get(temp_url, impersonate="chrome110")
            next_url = f"{parsed.scheme}://{parsed.hostname}/go/{id}"
            for _ in range(2):
                if request.headers.get('Location'): 
                    break
                bs4 = BeautifulSoup(request.content, 'lxml')
                inputs = bs4.form.findAll("input", {"name": re.compile(r"token$")})
                data = { input.get('name'): input.get('value') for input in inputs }
                data['x-token'] = self.recaptcha_v3_bypass()
                        
                request = client.post(next_url, data=data, headers={'content-type': 'application/x-www-form-urlencoded'}, allow_redirects=False, impersonate="chrome110")
                next_url = f"{parsed.scheme}://{parsed.hostname}/xreallcygo/{id}"
                
            return request.headers.get('Location')
        except Exception:
            time.sleep(1)
            self.bypass_ouo_io(url)

    def bypass_ads(self, url_list):
        bypassed_links = []

        self.set_console_title(f"Bypassing AD Links")

        for url in url_list:
            if "1link.club" in url:
                bypassed_links.append(self.bypass_1link_club(url))
            elif "ouo.io" or "ouo.press" in url:
                bypassed_links.append(self.bypass_ouo_io(url))

        return bypassed_links
 
    def ryujinx_apply_updates(self, update_files, game_id):
        updates_json = {"selected": "","paths": []}

        games_folder = os.path.join(os.getenv('APPDATA'), 'Ryujinx', 'games', game_id.lower())

        os.makedirs(games_folder, exist_ok=True)
        
        updates_json_path = os.path.join(games_folder, "updates.json")

        if os.path.exists(updates_json_path):
            with open(updates_json_path, "r", encoding="utf-8") as json_file:
                updates_json = json.load(json_file)
        
        for file in update_files:
            updates_json["selected"] = file
            updates_json["paths"].append(file)
            
        with open(updates_json_path, "w", encoding="utf-8") as json_file:
            json.dump(updates_json, json_file, ensure_ascii=False)
    
    def extract_rar(self, rar_file, extraction_path):
        extracted_files = []
        try:
            subprocess.run(["bin\\UnRAR.exe", "x", rar_file, extraction_path, "-y"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            result = subprocess.run(["bin\\UnRAR.exe", "lb", rar_file], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            files_in_rar = result.stdout.strip().split('\n')
            for file in files_in_rar:
                version_match = re.search(r'\[v(\d+)\]', file)
                if version_match:
                    if int(version_match.group(1)) != 0 and int(version_match.group(1)) % 65536 == 0: # 2^16
                        extracted_files.append(os.path.join(extraction_path, file))
        except subprocess.CalledProcessError as e:
            print(f"[!] Error extracting {rar_file}: {e}")
        return extracted_files

    def extract_all_files(self, directory_list):
        update_files = []
        multiple_parts = []
        for directory in directory_list:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if file.endswith(".rar"):
                        rar_file = os.path.join(root, file)
                        if ".part" in rar_file and not ".part1" in rar_file:
                            multiple_parts.append(file)
                            continue
                        updates = self.extract_rar(rar_file, os.path.dirname(rar_file))
                        if updates:
                            update_files.extend(updates)
                        os.remove(rar_file)
        for files in multiple_parts:
            os.remove(files)
        return update_files

    def download_files(self, url_list, game_title, game_id):
        options = OptionsLoader.load_options()
        fichier = Fichier(options)
        gofile = GOFile(options)
        qiwi = Qiwi(options)

        for url in url_list:
            self.set_console_title(f"Processing URL: {url}")
            if "1fichier" in url:
                if "&" in url:
                    url = url.split('&')[0]
                fichier.apply_bypass()
                fetched_download = fichier.fetch_download(url)
                fichier.download_from_url(fetched_download[0], fetched_download[1], game_title)
            elif "gofile" in url:
                fetched_download = gofile.fetch_download(url)
                gofile.download_from_url(fetched_download[0], fetched_download[1], game_title)
            elif "qiwi" in url:
                fetched_download = qiwi.fetch_download(url)
                qiwi.download_from_url(fetched_download[0], fetched_download[1], game_title)

        extracted_files = self.extract_all_files([options["games_folder"], options["updates_folder"], options["dlc_folder"]])
        if options["ryujinx_apply_updates"] and extracted_files:
            self.ryujinx_apply_updates(extracted_files, game_id)

def main():
    rom_parser = SwitchROM()
    rom_parser.set_console_title(f"Idling")

    search_query = input("Game Name: ")
    game_link = rom_parser.search_game(search_query)

    game_title, game_id, ad_links = rom_parser.get_game_rom(game_link)
    fichier_links = rom_parser.bypass_ads(ad_links)
    
    rom_parser.download_files(fichier_links, game_title, game_id)

    rom_parser.session.close()

    rom_parser.set_console_title(f"Idling")

    input()

if __name__ == "__main__":    
    if ctypes.windll.shell32.IsUserAnAdmin() == False:
        print("[!] Admin privileges needed for 1fichier bypass")
        exit()
    main()