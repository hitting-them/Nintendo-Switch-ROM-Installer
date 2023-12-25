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

class FichierBypass:
    def __init__(self, options):
        self.session = HTMLSession()
        self.games_folder = options["games_folder"]
        self.updates_folder = options["updates_folder"]
        self.dlc_folder = options["dlc_folder"]

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
        except Exception as e:
            print(f"[!] Error fetching download: {e}")
            exit("[!] File is possibly removed from 1fichier")

    def download_from_url(self, url, file_name, game_title):
        with self.session.get(url, stream=True) as response:
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
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        file.write(chunk)
                        downloaded_size += len(chunk)
                        self.update_console_title(file_name, downloaded_size, total_size, start_time)

    def update_console_title(self, file_name, downloaded_size, total_size, start_time):
        percentage = (downloaded_size / total_size) * 100
        elapsed_time = time.time() - start_time
        download_speed = downloaded_size / elapsed_time if elapsed_time > 0 else 0
        remaining_size = total_size - downloaded_size
        eta_seconds = remaining_size / download_speed if download_speed > 0 else 0

        eta_formatted = time.strftime("%H:%M:%S", time.gmtime(eta_seconds))

        ctypes.windll.kernel32.SetConsoleTitleW(f"@hitting-them - Switch Rom Installer | {file_name} - {downloaded_size/1024/1024:.2f}MB / {total_size/1024/1024:.2f}MB - {percentage:.2f}% | ETA: {eta_formatted}")

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
                fichier_element = selected_option.find("strong", string="1Fichier")
                if fichier_element:
                    fichier_downloads = fichier_element.find_parent().find_all("a")
                    for download_link in fichier_downloads:
                        download_links.append(download_link["href"])
                else:
                    single_fichier_element = selected_option.find("a", string="1Fichier")
                    download_links.append(single_fichier_element["href"])
        
            return game_title, download_links
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

        parsed = urlparse(temp_url)
        id = temp_url.split('/')[-1]
        request = client.get(temp_url, impersonate="chrome110")
        next_url = f"{parsed.scheme}://{parsed.hostname}/go/{id}"
        try:
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
            elif "ouo.io" in url:
                bypassed_links.append(self.bypass_ouo_io(url))

        return bypassed_links
 
    def ryujinx_apply_updates(self, update_files):
        updates_json = {"selected": "","paths": []}

        game_id = re.search(r'\[([^]]{11,})\]', update_files[0]).group(1)
        
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
                if int(version_match.group(1)) != 0 and int(version_match.group(1)) % 65536 == 0: # 2^16
                    extracted_files.append(os.path.join(extraction_path, file))
        except subprocess.CalledProcessError as e:
            print(f"[!] Error extracting {rar_file}: {e}")
        return extracted_files

    def extract_all_files(self, directory_list):
        update_files = []
        for directory in directory_list:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if file.endswith(".rar"):
                        rar_file = os.path.join(root, file)
                        if ".part" in rar_file and not ".part1" in rar_file:
                            os.remove(rar_file)
                            continue
                        updates = self.extract_rar(rar_file, os.path.dirname(rar_file))
                        if updates:
                            update_files.extend(updates)
                        os.remove(rar_file)

        return update_files

    
    def download_files(self, url_list, game_title):
        options = OptionsLoader.load_options()
        fichier = FichierBypass(options)

        for url in url_list:
            if "&" in url:
                url = url.split('&')[0]
            
            self.set_console_title(f"Applying Download Bypass")
            fichier.apply_bypass()
            fetched_download = fichier.fetch_download(url)
            fichier.download_from_url(fetched_download[0], fetched_download[1], game_title)

            extracted_files = self.extract_all_files([options["games_folder"], options["updates_folder"], options["dlc_folder"]])
            if options["ryujinx_apply_updates"] and extracted_files:
                self.ryujinx_apply_updates(extracted_files)
  
def main():
    rom_parser = SwitchROM()
    rom_parser.set_console_title(f"Idling")

    search_query = input("Game Name: ")
    game_link = rom_parser.search_game(search_query)

    game_title, ad_links = rom_parser.get_game_rom(game_link)
    fichier_links = rom_parser.bypass_ads(ad_links)
    
    rom_parser.download_files(fichier_links, game_title)

    rom_parser.session.close()

    rom_parser.set_console_title(f"Idling")

    input()

if __name__ == "__main__":    
    if ctypes.windll.shell32.IsUserAnAdmin() == False:
        print("[!] Admin privileges needed for 1fichier bypass")
        exit()
    main()