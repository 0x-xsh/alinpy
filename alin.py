import logging
import telebot
import requests
import json
from datetime import datetime, timedelta
import time
import threading

# Set your Telegram bot token here
TELEGRAM_BOT_TOKEN = "7540457118:AAEsbNbi7aM23Xx-Sr7pQhgFaRUgVmobTJQ"

# Define the chat ID or user ID to receive the startup message
STARTUP_CHAT_ID = "818102635"

# API endpoint URL
API_URL = "https://api.al-in.fr/api/dmo/public_housing_offers"

# Store the processed house IDs and the current postal codes
processed_house_ids = set()
current_postal_codes = []
should_fetch = True
fetch_thread = None

# Initialize Telebot for sending messages
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# File to store the latest postal codes
POSTAL_CODE_FILE = 'latest_postal_code.txt'

def send_telegram_message(text):
    try:
        bot.send_message(chat_id=STARTUP_CHAT_ID, text=text)
    except telebot.apihelper.ApiException as e:
        logging.error(f"Error sending message: {e}")
        time.sleep(5)
        send_telegram_message(text)

def fetch_housing_offers(postal_codes):
    global processed_house_ids

    # Get today's date in the format YYYY-MM-DD
    yesterday = (datetime.today() - timedelta(days=1)).strftime('%Y-%m-%d')
    today = datetime.today().strftime('%Y-%m-%d')

    # Construct the API request with multiple postal codes
    params = {
        "publication_end_date[$gte]": yesterday,
        "date_publication_start[$lte]": today,
        "rent_with_charges[$gte]": 2,
    }

    # Add postal codes to the parameters
    for index, postal_code in enumerate(postal_codes):
        params[f"$or[{index}][postal_code]"] = postal_code

    # Make the API request
    response = requests.get(API_URL, params=params)
    data = json.loads(response.text)

    # Check for new housing offers
    if "data" in data:
        for offer in data["data"]:
            offer_id = offer["id"]
            if offer_id not in processed_house_ids:
                processed_house_ids.add(offer_id)
                housing_info = offer["attributes"]
                address = housing_info["address"]
                rent = housing_info["rent_with_charges"]
                availability_date = housing_info["availability_date"]
                logging.info(f"New offer found: Address: {address}, Rent: {rent} EUR, Available from: {availability_date}")
                send_telegram_message(f"New offer push: Address: {address}, Rent: {rent} EUR, Available from: {availability_date}")
            else:
                logging.info(f"Offer {offer_id} has already been processed.")
    else:
        logging.info("No housing offers found for the specified postal codes.")

def fetch_and_loop():
    global should_fetch
    while should_fetch:
        if current_postal_codes:
            fetch_housing_offers(current_postal_codes)
        time.sleep(5)

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Welcome! Use /postal [postal code1] [postal code2] ... to search for housing offers.")
    # Check if there's a postal code saved in the file
    try:
        with open(POSTAL_CODE_FILE, 'r') as file:
            saved_postal_codes = file.read().strip().split(',')
            if saved_postal_codes:
                # Trigger the /postal command with saved postal codes
                handle_postal_codes(saved_postal_codes)
    except FileNotFoundError:
        pass

@bot.message_handler(commands=['postal'])
def postal(message):
    global current_postal_codes, processed_house_ids, should_fetch, fetch_thread
    try:
        # Extract postal codes from message text
        postal_codes = message.text.split()[1:]

        # Check if postal codes are provided and valid
        if not postal_codes:
            bot.reply_to(message, "Please provide at least one postal code. Usage: /postal [postal code1] [postal code2] ...")
            return

        handle_postal_codes(postal_codes)
        
    except Exception as e:
        bot.reply_to(message, f"An error occurred: {str(e)}")

def handle_postal_codes(postal_codes):
    global current_postal_codes, processed_house_ids, should_fetch, fetch_thread
    current_postal_codes = postal_codes
    processed_house_ids.clear()  # Clear the set to allow tracking of new offers

    # Override the postal codes in the file
    with open(POSTAL_CODE_FILE, 'w') as file:
        file.write(','.join(postal_codes))

    # Notify the user and start the fetch loop
    send_telegram_message(f"Postal codes set to {', '.join(postal_codes)}. Searching for offers...")

    # Stop the previous fetch thread if it's running
    if fetch_thread and fetch_thread.is_alive():
        should_fetch = False
        fetch_thread.join()  # Wait for the thread to stop
        should_fetch = True

    # Start a new fetch loop in a separate thread
    fetch_thread = threading.Thread(target=fetch_and_loop)
    fetch_thread.start()

def main():
    send_telegram_message("Bot has started successfully!")
    try:
        with open(POSTAL_CODE_FILE, 'r') as file:
            saved_postal_codes = file.read().strip().split(',')
            if saved_postal_codes[0] != '':
                
                # Trigger the /postal command with saved postal codes
                handle_postal_codes(saved_postal_codes)
    except FileNotFoundError:
        pass
    bot.polling(none_stop=True)

if __name__ == "__main__":
    main()
