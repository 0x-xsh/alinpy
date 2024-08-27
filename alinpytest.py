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

# Store the processed house IDs with their last "offer_status_updated_at"
processed_offers = {}
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

def logAndSend(text):
    print(text)
    send_telegram_message(text)

def fetch_housing_offers(postal_codes):
    global processed_offers

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
            offer_status_updated_at = offer["attributes"]["offer_status_updated_at"]

            if offer_id not in processed_offers or processed_offers[offer_id] != offer_status_updated_at:
                processed_offers[offer_id] = offer_status_updated_at
                housing_info = offer["attributes"]
                address = housing_info["address"]
                rent = housing_info["rent_with_charges"]
                availability_date = housing_info["availability_date"]
                date_publication_start = housing_info["date_publication_start"]

                logAndSend(f"New offer: Address: {address}, Rent: {rent} EUR, Available from: {availability_date}, published at: {date_publication_start}, status updated at: {offer_status_updated_at}")
            else:
                print(f"Offer {offer_id} has already been processed with the same status update.")
    else:
        logAndSend("No housing offers found for the specified postal codes.")

def fetch_and_loop():
    global should_fetch
    while should_fetch:
        if current_postal_codes:
            fetch_housing_offers(current_postal_codes)
        time.sleep(5)

def handle_postal_codes(postal_codes):
    global current_postal_codes, processed_offers, should_fetch, fetch_thread
    current_postal_codes = postal_codes
    processed_offers.clear()  # Clear the dictionary to allow tracking of new offers

    # Override the postal codes in the file
    with open(POSTAL_CODE_FILE, 'w') as file:
        file.write(','.join(postal_codes))

    # Notify the user and start the fetch loop
    logAndSend(f"Postal codes set to {', '.join(postal_codes)}. Searching for offers...")

    # Stop the previous fetch thread if it's running
    if fetch_thread and fetch_thread.is_alive():
        should_fetch = False
        fetch_thread.join()  # Wait for the thread to stop
        should_fetch = True

    # Start a new fetch loop in a separate thread
    fetch_thread = threading.Thread(target=fetch_and_loop)
    fetch_thread.start()

def main():
    logAndSend("Bot has started successfully!")

    try:
        with open(POSTAL_CODE_FILE, 'r') as file:
            saved_postal_codes = file.read().strip().split(',')
            if saved_postal_codes[0] != '':
                # Trigger the handling of saved postal codes
                handle_postal_codes(saved_postal_codes)
    except FileNotFoundError:
        logAndSend("ERROR: file not found")

    # Get postal codes from user input
    while True:
        user_input = input("Enter postal codes separated by spaces (or 'exit' to quit): ")
        if user_input.lower() == 'exit':
            should_fetch = False
            if fetch_thread and fetch_thread.is_alive():
                fetch_thread.join()  # Wait for the thread to stop
            break

        postal_codes = user_input.split()
        handle_postal_codes(postal_codes)

if __name__ == "__main__":
    main()
