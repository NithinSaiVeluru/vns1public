import time
import schedule
from hdwallet import HDWallet
from tronpy.keys import PrivateKey
from eth_keys import keys
from eth_utils import decode_hex, to_checksum_address
import mnemonic
import secp256k1 as ice
from multiprocessing import Pool, cpu_count, Manager
import requests
from threading import Lock
import time
import os
from multiprocessing import Manager
from os import system, name
from datetime import datetime
from rich.console import Console
from bloomfilter import BloomFilter
import json
import random
import configparser
from functools import partial

console = Console()
maxcpucount = os.cpu_count()
file_lock = Lock()
telegram_lock = Lock()
start_time = time.perf_counter()
# Дополнительные счетчики
total_mnemonics_checked = 0
total_addresses_checked = 0
total_found = 0
total_false_found = 0
api_key = "VUBZ8JZAY69WW9QIYQ2G9T2EUBM31JJG59"
start_time = time.perf_counter()
version = "version 0.5 by 14.08.2023"

def main_text():
    console.print(f'[I] [cyan]Version:[/cyan] [red]{version}[/red]'
                f'\n[I] [cyan]Execution Started:[/cyan] [red]{date_str()}[/red]'
                f'\n[I] [cyan]Max Available Cores:[/cyan] [green]{maxcpucount}[/green]\n'
                f'\n[cyan]Welcome to our multi-threaded cryptocurrency address matching tool! This application is designed to find matches in the address lists of Bitcoin, Ethereum, and Tron.'
                f'\n[red]_______________________________\n')

def save_to_config(use_telegram, bot_token, chat_id, symbols, derivation_depths, db_paths_by_symbol, choice_mode, print_mode, cores):
    config = configparser.ConfigParser()
    config_path = 'config.ini'

    config.add_section('general')
    config.set('general', 'use_telegram', use_telegram)
    if use_telegram.lower() == 'yes':
        config.set('general', 'bot_token', bot_token)
        config.set('general', 'chat_id', chat_id)

    for symbol in symbols:
        config.add_section(symbol)
        config.set(symbol, 'derivation_depth', str(derivation_depths[symbol]))
        config.set(symbol, 'db_paths', ";".join(db_paths_by_symbol[symbol]))

    config.set('general', 'choice_mode', choice_mode)
    config.set('general', 'print_mode', print_mode)
    config.set('general', 'cores', str(cores))

    with open(config_path, 'w') as config_file:
        config.write(config_file)

def load_from_config():
    config = configparser.ConfigParser()
    config_path = 'config.ini'

    config.read(config_path)

    use_telegram = config.get('general', 'use_telegram')
    bot_token = config.get('general', 'bot_token') if 'bot_token' in config['general'] else None
    chat_id = config.get('general', 'chat_id') if 'chat_id' in config['general'] else None

    symbols = config.sections()[1:]  # Excluding the 'general' section
    derivation_depths = {}
    db_paths_by_symbol = {}
    for symbol in symbols:
        derivation_depths[symbol] = int(config.get(symbol, 'derivation_depth'))
        db_paths_by_symbol[symbol] = config.get(symbol, 'db_paths').split(';')

    choice_mode = config.get('general', 'choice_mode')
    print_mode = config.get('general', 'print_mode')
    cores = int(config.get('general', 'cores'))

    return use_telegram, bot_token, chat_id, symbols, derivation_depths, db_paths_by_symbol, choice_mode, print_mode, cores

def get_telegram_config():
    config = configparser.ConfigParser()
    config_path = 'config.ini'
    main_text()
    use_telegram = console.input('[cyan]Do you want to send information to Telegram? ([green]yes/[red]no): ')
    if use_telegram.lower() == 'yes':
        bot_token = console.input('[cyan]Enter bot token: ')
        chat_id = console.input('[cyan]Enter chat id: ')
    else:
        bot_token = None
        chat_id = None

    coin_mapping = {1: "BTC", 2: "ETH", 3: "TRX", 4: "Token"}
    console.print('[cyan]Enter the numbers of the coins you want to search\nYou can choose a different search, if you only want BTC choose 1, if TRX and Token then 3,4')
    chosen_coins = console.input("\n[cyan]Choose : [green](1 - BTC | 2 - ETH | 3 - TRX | 4 - Token) : ")
    chosen_coins = chosen_coins.split(",")
    symbols = [coin_mapping[int(coin)] for coin in chosen_coins]

    # Displaying the text only once before the loop for each chosen coin
    console.print(f"\n[cyan]Derivation depth refers to the number of child keys derived from the parent key for addresses."
                        f"\n[cyan]For example, a derivation depth of 5 would mean generating 5 addresses for each mnemonic phrase."
                        f"\n[cyan]The depth of the derivation will be marked in red : [green]m/44'/0'/0/0/[red]0'.\n")

    # Ask for derivation depth for each chosen coin
    derivation_depths = {}
    db_paths_by_symbol = {}
    console.print('[cyan]Example from a folder : [green]bf_base/btc.bf;btc1.bf,btc4.bf')
    console.print('[cyan]Example without a folder : [green]btc.bf;btc1.bf,btc4.bf\n')
    console.print('[cyan]It is necessary to enter the path for each coin separately, enter it for bitcoin, then it will be for ether')
    console.print('[green]__________________________')
    for symbol in symbols:
        depth = console.input("[cyan]Enter the derivation depth for [green]{}: ".format(symbol))
        derivation_depths[symbol] = int(depth)
        db_paths_input = console.input(f"[cyan]Enter the path(s) to the address database(s) for [green]{symbol} [cyan](separate with ';' if multiple): ").strip()
        db_paths = db_paths_input.split(';')
        db_paths_by_symbol[symbol] = db_paths

    choice_mode = console.input("\n[cyan]Select a mode: ([green]1[/green] - reading from a file, [green]2[/green] - generating random mnemonics): ")
    print_mode = console.input("\n[cyan]Select [green]1[/green] for large output | [green]2[/green] for short output: ")
    cores = int(console.input("\n[cyan]Enter the number of cores to use (0 for all available): "))

    save_choice = console.input("[cyan]Do you want to save these settings for a quick start next time? ([green]yes/[red]no): ")
    if save_choice.lower() == 'yes':
        save_to_config(use_telegram, bot_token, chat_id, symbols, derivation_depths, db_paths_by_symbol, choice_mode, print_mode, cores)

    return use_telegram, bot_token, chat_id, symbols, derivation_depths, db_paths_by_symbol, choice_mode, print_mode, cores


def check_and_read_config():
    # Check if config.ini exists
    if os.path.exists("config.ini"):
        config = configparser.ConfigParser()
        config.read("config.ini")
        
        # Ask user if they want to use previous settings
        use_previous = console.input("\n[cyan]Do you want to use previous settings? ([green]Yes[/green]/No): ").lower()
        if use_previous == "yes":
            settings = dict(config["SETTINGS"])
            return settings
    return None

def cls():
    system('cls' if name=='nt' else 'clear')
def date_str():
    now = datetime.now()
    return now.strftime("%Y/%m/%d/, %H:%M:%S")

def update_status_small(total_mnemonics_checked, total_addresses_checked, elapsed_time, total_found, total_false_found):
    console.print(f"[cyan]Checked mnemonics: [green]{total_mnemonics_checked}, "
                    f"[cyan]Verified addresses: [green]{total_addresses_checked}, "
                    f"[cyan]Time has passed: [green]{round(elapsed_time, 1):.1f}, "
                    f"[cyan]Found FALSE: [green]{total_false_found}, "
                    f"[cyan]Found: [green]{total_found}", end='\r')

def update_status_big(symbol, words, prefix, account, change, address_index, address, private_key):
    console.print(f"[cyan]Mnemonic [blue]{symbol}: [green]{words}")
    console.print(f"[cyan]Path: [blue]m/{prefix}'/0'/{account}'/{change}/{address_index}")
    console.print(f"[cyan]Address [blue]{symbol}: [green]{address}")
    console.print(f"[cyan]Private Key [blue]{symbol}: [green]{private_key}")
    console.print('[cyan]______________')

def send_status_to_telegram():
    elapsed_time = time.perf_counter() - start_time
    message_text = f"Checked mnemonics: {total_mnemonics_checked}, " \
                   f"Verified addresses: {total_addresses_checked}, " \
                   f"Time has passed: {round(elapsed_time, 1)}, " \
                   f"Found: {total_found}"
    with telegram_lock:
        send_telegram_message("tg_id", "chat_id", message_text, view)

schedule.every(1).minutes.do(send_status_to_telegram)

def view(symbol, words, prefix, account, change, address_index, address, private_key, use_telegram, bot_token, chat_id):
    console.print(f'[green]FOUND! | FOUND! | FOUND!')
    console.print(f"[cyan]Mnemonic [blue]{symbol}: [green]{words}")
    console.print(f"[cyan]Path: [blue]m/{prefix}'/0'/{account}'/{change}/{address_index}")
    console.print(f"[cyan]Address [blue]{symbol}: [green]{address}")
    console.print(f"[cyan]Private Key [blue]{symbol}: [green]{private_key}")
    console.print('[cyan]______________\n')
    
    # Create a message for Telegram
    message_text = (f"FOUND! | FOUND! | FOUND!\n"
                    f"Mnemonic {symbol}: {words}\n"
                    f"Path: m/{prefix}'/0'/{account}'/{change}/{address_index}\n"
                    f"Address {symbol}: {address}\n"
                    f"Private Key {symbol}: {private_key}\n"
                    f"______________\n")
    
    # Send the message to Telegram
    with telegram_lock:
        send_telegram_message(message_text, use_telegram, bot_token, chat_id)

def send_telegram_message(text, use_telegram, bot_token, chat_id):
    if use_telegram.lower() == 'yes':
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": text
        }
        response = requests.post(url, data=data)
        return response.json()

def get_eth_balance(wallet_address):
    try:
        url = f"https://api.etherscan.io/api?module=account&action=balance&address={wallet_address}&tag=latest&apikey={api_key}"
        response = requests.get(url)
        data = response.json()
        if data["status"] == "1":
            balance_wei = int(data["result"])
            balance_eth = balance_wei / 10**18
            return balance_eth
        else:
            return None
    except Exception as e:
        print(f"Error getting ETH balance: {e}")
        return None

def get_btc_balance(wallet_address):
    try:
        url = f"https://blockchain.info/q/addressbalance/{wallet_address}?confirmations=6"
        response = requests.get(url)
        if response.status_code == 200:
            balance_satoshi = int(response.text)
            balance_btc = balance_satoshi / 10**8
            return balance_btc
        else:
            return None
    except Exception as e:
        print(f"Error getting BTC balance: {e}")
        return None

def get_trx_balance(wallet_address):
    try:
        url = f"https://apilist.tronscan.org/api/account?address={wallet_address}"
        response = requests.get(url)
        data = json.loads(response.text)
        if response.status_code == 200:
            balance = float(data["balance"])
            return balance
        else:
            return None
    except Exception as e:
        print(f"Error getting TRX balance: {e}")
        return None

def read_addresses_with_progress(file_paths, coin_name):
    bloom_filters = {}
    for file_path in file_paths:
        console.print(f"[cyan]Loading {coin_name} Bloom Filter from [green]{file_path}:")
        with open(file_path, "rb") as fp:
            bloom_filter = BloomFilter.load(fp)
        console.print(f"[cyan]Loaded {coin_name} Bloom Filter with [green]{len(bloom_filter)} [cyan]items\n")
        bloom_filters[file_path] = bloom_filter
    return bloom_filters

def check_address_match(address, bloom_filters):
    for bloom_filter in bloom_filters.values():
        if address in bloom_filter:
            return True
    return False

def generate_address_from_mnemonic(args, use_telegram, bot_token, chat_id):
    words, symbol, addresses, print_mode, choice_mode, total_mnemonics_checked, total_addresses_checked, total_found, total_false_found, start_time, derivation_depths = args
    Compr = None
    total_mnemonics_checked.value += 1
    path_mapping = {
        'BTC': 0,
        'ETH': 60,
        'TRX': 195
    }
    symbol_for_path = symbol if symbol != 'Token' else 'ETH'
    path = path_mapping[symbol_for_path]

    # Create the HDWallet object once for the mnemonic
    symbol_for_wallet = symbol if symbol != 'Token' else 'ETH'
    hdwallet = HDWallet(symbol=symbol_for_wallet, use_default_path=False)
    hdwallet.from_mnemonic(mnemonic=words)

    # Define prefix based on the symbol
    prefixes = [44] if symbol != 'BTC' else [44, 49, 84]

    for prefix in prefixes:
        for account in range(1):
            for change in range(1):
                for address_index in range(derivation_depths[symbol]):  # use the depth provided by the user
                    
                    # Reset the path for the HDWallet object
                    hdwallet.from_index(prefix, hardened=True)
                    hdwallet.from_index(path, hardened=True)
                    hdwallet.from_index(account, hardened=True)
                    hdwallet.from_index(change)
                    hdwallet.from_index(address_index)
                    private_key = hdwallet.private_key()
    for prefix in prefixes: 
        for account in range(1):
            for change in range(1):
                for address_index in range(derivation_depths[symbol]):  # use the depth provided by the user
                    symbol_for_wallet = symbol if symbol != 'Token' else 'ETH'
                    hdwallet = HDWallet(symbol=symbol_for_wallet, use_default_path=False)
                    hdwallet.from_mnemonic(mnemonic=words)
                    hdwallet.from_index(prefix, hardened=True)
                    hdwallet.from_index(path, hardened=True)
                    hdwallet.from_index(account, hardened=True)
                    hdwallet.from_index(change)
                    hdwallet.from_index(address_index)
                    private_key = hdwallet.private_key()

                    if symbol == 'TRX':
                        priv_key_obj = PrivateKey(bytes.fromhex(private_key))
                        address = priv_key_obj.public_key.to_base58check_address()
                        checkaddr = '0x' + ice.address_to_h160(address)  # Преобразование адреса TRON в формат Hash160
                    elif symbol == 'ETH':
                        private_key_bytes = decode_hex(private_key)
                        private_key_obj = keys.PrivateKey(private_key_bytes)
                        public_key = private_key_obj.public_key
                        address = to_checksum_address(public_key.to_address())
                        checkaddr = address  # Использование самого адреса Ethereum для поиска совпадений
                    elif symbol == 'BTC':
                        private_key_bit = int(private_key, 16)
                        mapping = {44: 0, 49: 1, 84: 2}
                        Compr = ice.privatekey_to_address(mapping[prefix], True, private_key_bit)
                        address = Compr
                        checkaddr = address
                    total_addresses_checked.value += 1

                    if symbol == 'ETH':
                        address_eth_checking = address[2:]
                        address_token_checking = address[2:]

                        # Проверка для 'Token', если 'Token' присутствует в 'addresses'
                        if 'Token' in addresses and check_address_match(address_token_checking, addresses['Token']):
                            try:
                                eth_balance = get_eth_balance(address)
                            except Exception as e:
                                print(f"Error getting ETH balance: {e}")
                                eth_balance = None
                            total_false_found.value += 1
                            view(symbol, words, prefix, account, change, address_index, address, private_key, use_telegram, bot_token, chat_id)
                            with open("FOUNDETH.txt", "a") as file:
                                file.write(f"Mnemonic: {words}\n")
                                file.write(f"Path: m/{prefix}'/{path}'/{account}'/{change}/{address_index}\n")
                                file.write(f"Private Key: {private_key}\n")
                                file.write(f"Адрес Ethereum: {address}\n")
                                file.write(f"ETH balance: {eth_balance}\n")
                                file.write("------------------\n")
                            if eth_balance is not None and eth_balance > 0:
                                total_found.value += 1
                                total_false_found.value -= 1
                                print("Match found for Token with balance!\n")
                        elif check_address_match(address_eth_checking, addresses['ETH']):
                            try:
                                eth_balance = get_eth_balance(address)
                            except Exception as e:
                                print(f"Error getting ETH balance: {e}")
                                eth_balance = None
                            total_false_found.value += 1
                            view(symbol, words, prefix, account, change, address_index, address, private_key, use_telegram, bot_token, chat_id)
                            with open("FOUNDETH.txt", "a") as file:
                                file.write(f"Mnemonic: {words}\n")
                                file.write(f"Path: m/{prefix}'/{path}'/{account}'/{change}/{address_index}\n")
                                file.write(f"Private Key: {private_key}\n")
                                file.write(f"Адрес Ethereum: {address}\n")
                                file.write(f"ETH balance: {eth_balance}\n")
                                file.write("------------------\n")
                            if eth_balance is not None and eth_balance > 0:
                                total_found.value += 1
                                total_false_found.value -= 1
                                print("Match found for Token with balance!\n")

                    elif symbol == 'TRX':
                        if check_address_match(checkaddr, addresses['TRX']):
                            try:
                                trx_balance = get_trx_balance(address)
                            except Exception as e:
                                print(f"Error getting TRX balance: {e}")
                                trx_balance = None
                            total_false_found.value += 1
                            view(symbol, words, prefix, account, change, address_index, address, private_key, use_telegram, bot_token, chat_id)
                            with open("FOUNDRTX.txt", "a") as file:
                                file.write(f"Mnemonic: {words}\n")
                                file.write(f"Path: m/{prefix}'/{path}'/{account}'/{change}/{address_index}\n")
                                file.write(f"Private Key: {private_key}\n")
                                file.write(f"Адрес Tron: {address}\n")
                                file.write(f"TRX balance: {trx_balance}\n")
                            if trx_balance is not None and trx_balance > 0:
                                total_found.value += 1
                                total_false_found.value -= 1
                                print("Match found for TRX with balance!\n")

                    elif symbol == 'BTC':
                        if check_address_match(checkaddr, addresses['BTC']):
                            try:
                                btc_balance = get_btc_balance(address)
                            except Exception as e:
                                print(f"Error getting BTC balance: {e}")
                                btc_balance = None
                            total_false_found.value += 1
                            view(symbol, words, prefix, account, change, address_index, address, private_key, use_telegram, bot_token, chat_id)
                            with open("FOUNDBTC.txt", "a") as file:
                                file.write(f"Mnemonic: {words}\n")
                                file.write(f"Path: m/{prefix}'/{path}'/{account}'/{change}/{address_index}\n")
                                file.write(f"Private Key: {private_key}\n")
                                file.write(f"Адрес Bitcoin: {address}\n")
                            if btc_balance is not None and btc_balance > 0:
                                total_found.value += 1
                                total_false_found.value -= 1
                                print("Match found for BTC with balance!\n")

                    elapsed_time = time.perf_counter() - start_time
                    if print_mode == "1":
                        update_status_big(symbol, words, prefix, account, change, address_index, address, private_key)
                    else:
                        update_status_small(total_mnemonics_checked.value, total_addresses_checked.value, elapsed_time, total_found.value, total_false_found.value)

    return total_mnemonics_checked, total_addresses_checked, total_found

def process_mnemonics(mnemonic_phrases, use_telegram , bot_token, chat_id, addresses, print_mode, choice_mode, cores, total_mnemonics_checked, total_addresses_checked, total_found, total_false_found, start_time, derivation_depths):
    symbols = addresses.keys()
    with Pool(processes=cores) as pool:
        args = [(mnemonic_phrase, symbol, addresses, print_mode, choice_mode, total_mnemonics_checked, total_addresses_checked, total_found, total_false_found, start_time, derivation_depths) for mnemonic_phrase in mnemonic_phrases for symbol in symbols]
        pool.map(partial(generate_address_from_mnemonic, use_telegram=use_telegram, bot_token=bot_token, chat_id=chat_id), args)

def main():
    config_path = 'config.ini'
    
    # Check if config file exists and load previous settings or get new ones
    if os.path.exists(config_path):
        choice = console.input("[cyan]Found previous settings. Do you want to use them? ([green]yes/[red]no): ")
        if choice.lower() == 'yes':
            use_telegram, bot_token, chat_id, symbols, derivation_depths, db_paths_by_symbol, choice_mode, print_mode, cores = load_from_config()
        else:
            use_telegram, bot_token, chat_id, symbols, derivation_depths, db_paths_by_symbol, choice_mode, print_mode, cores = get_telegram_config()
    else:
        use_telegram, bot_token, chat_id, symbols, derivation_depths, db_paths_by_symbol, choice_mode, print_mode, cores = get_telegram_config()

    # Clear screen and display introductory messages
    cls()
    main_text()

    # Load the address databases
    addresses = {}
    for symbol in symbols:
        db_paths = db_paths_by_symbol[symbol]
        addresses[symbol] = read_addresses_with_progress(db_paths, symbol)

    # Initialize multi-processing variables
    manager = Manager()
    total_mnemonics_checked = manager.Value('i', 0)
    total_addresses_checked = manager.Value('i', 0)
    total_found = manager.Value('i', 0)
    total_false_found = manager.Value('i', 0)

    cores = cpu_count() if cores == 0 else cores

    start_time = time.perf_counter()  # Initialize start_time before the loop

    # Mnemonic processing
    if choice_mode == "1":
        filename = "mnemonic.txt"  # Assuming a default filename. Can be changed as per requirement.
        with open(filename, "r") as file:
            mnemonic_phrases = file.read().splitlines()
            # Assuming process_mnemonics is a function in your code that processes mnemonics.
            process_mnemonics(mnemonic_phrases, use_telegram , bot_token, chat_id, addresses, print_mode, choice_mode, cores, total_mnemonics_checked, total_addresses_checked, total_found, total_false_found, start_time, derivation_depths)
    else:
        batch_size = 1500  # Generate as many mnemonics at a time as there are cores
        mnemonic_length_mapping = {1: 128, 2: 160, 3: 192, 4: 256, 5: "random"}
        chosen_length = console.input("\n[cyan]Enter the length of the mnemonic phrase [green](1 - 12 words, 2 - 15 words, 3 - 18 words, 4 - 24 words, 5 - random): ")
        chosen_length = mnemonic_length_mapping[int(chosen_length)]
        if chosen_length == "random":
            chosen_length = random.choice([128, 160, 192, 256])

        while True:  # Infinite loop to generate and process mnemonics
            mnemonic_phrases = []
            for _ in range(batch_size):
                new_mnemonic = mnemonic.Mnemonic("english").generate(strength=chosen_length)
                mnemonic_phrases.append(new_mnemonic)
            process_mnemonics(mnemonic_phrases, use_telegram , bot_token, chat_id, addresses, print_mode, choice_mode, cores, total_mnemonics_checked, total_addresses_checked, total_found, total_false_found, start_time, derivation_depths)

if __name__ == "__main__":
    main()
