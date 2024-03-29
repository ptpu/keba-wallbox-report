import csv
from datetime import datetime
import locale
import time
import requests
import os
import nextcloud_client
from dotenv import load_dotenv
from typing import List
from session import Session
from jinja2 import Environment, FileSystemLoader
from decimal import Decimal

def main():
    load_dotenv()
    download_data('chargingsession.csv')
    locale.setlocale(locale.LC_ALL, "de_DE")
    sessions = parse_csv('chargingsession.csv')
    sessions = list(filter(date_filter, sessions))
    sessions = list(reversed(sessions))
    consumption = map(lambda x: x.consumption, sessions)
    consumption = sum(consumption)
    
    env = Environment(loader=FileSystemLoader('templates'))
    template = env.get_template('report.html.j2')
    html = template.render(sessions=sessions, date=prev_month(), consumption=consumption, electricity_rate=Decimal(os.environ.get('electricity_rate')), electricity_basic_price=Decimal(os.environ.get('electricity_basic_price')))

    folder_path = os.path.join('reports', str(prev_month().year), str(prev_month().month))
    os.makedirs(folder_path, exist_ok=True)

    file_name = 'Report_{}{}.html'.format(prev_month().year, prev_month().month)
    file_path = os.path.join(folder_path, file_name)

    with open(file_path, 'w') as f:
        f.write(html)

    print(f'Data saved to {file_path}')

    upload_file(file_path, '{}/{}'.format(os.environ.get('nextcloud_remote_dir'), file_name))

def date_filter(x: Session):
    return x.end.year == prev_month().year and x.end.month == prev_month().month

def prev_month(date=datetime.today()):
    if date.month == 1:
        return date.replace(month=12,year=date.year-1)
    else:
        try:
            return date.replace(month=date.month-1)
        except ValueError:
            return prev_month(date=date.replace(day=date.day-1))

def authenticate():
    auth_url = 'http://{}/ajax.php'.format(os.environ.get('webui_ip'))
    body = {'username': os.environ.get('username'), 'password': os.environ.get('password')}
    response = requests.post(auth_url, json=body)
    return response.cookies if response.ok else None

def download_data(outputFile: str):
    download_url = 'http://{}/export.php?chargingsessions&t={}'.format(os.environ.get('webui_ip'), int(time.time()))

    cookies = authenticate()
    if cookies:
        download = requests.get(download_url, cookies=cookies)
        if download.ok:
            with open(outputFile, 'wb') as file:
                file.write(download.content)
            print(f'Data downloaded and saved to {outputFile}')
        else:
            print('Failed to download data.')
    else:
        print('Authentication failed.')

def parse_csv(csvFilePath: str) -> List[Session]:
    """
    Parse a CSV file containing charging session data and return a list of Session objects.

    Args:
        csvFilePath (str): The path to the CSV file to parse.

    Returns:
        List[Session]: A list of Session objects.
    """
    sessions = []

    with open(csvFilePath, encoding='utf-8') as csvf:
        csvReader = csv.DictReader(csvf, delimiter=';')

        sessions = [
            Session(
                row['Charging Station ID'],
                row['Serial'],
                row['RFID Card'],
                row['Status'],
                row['Start'],
                row['End'],
                row['Meter at start (Wh)'],
                row['Meter at end (Wh)']
            )
            for row in csvReader if row['Status'] == "CLOSED"
        ]

    return sessions

def upload_file(local_file: str, remote_file: str):
    nc = nextcloud_client.Client(os.environ.get('nextcloud_url'))
    nc.login(os.environ.get('nextcloud_user'), os.environ.get('nextcloud_password'))

    nc.put_file(remote_file, local_file)

    print(f'Report successfully uploaded to {remote_file}')

if __name__ == "__main__":
    main()