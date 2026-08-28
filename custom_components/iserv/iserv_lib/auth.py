import html
import logging
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import requests
from . import exceptions


class AuthClient:

    def __init__(self, username, password, iserv_url) -> None:
        self.username = username
        self._password = password
        # Bereinigt eventuelle 'https://' oder Pfadangaben
        self.iserv_url = (
            iserv_url.replace("https://", "").replace("http://", "").rstrip("/")
        )
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
        })
        self._IServSAT = None
        self._IServSATId = None
        self._IServSession = None

        self.login()

    def _follow_meta_and_links(self, response):
        """Folgt HTML-Meta-Refreshs und OAuth-Callback-Links im HTML-Body."""
        current_res = response
        for _ in range(6):
            soup = BeautifulSoup(current_res.text, "html.parser")

            # 1. OAuth Redirect-Link prüfen
            redirect_link = soup.find("a", href=re.compile(r"/iserv/app/authentication/redirect"))
            if redirect_link and redirect_link.get("href"):
                next_url = html.unescape(redirect_link["href"])
                next_url = urljoin(current_res.url, next_url)
                current_res = self._session.get(next_url, allow_redirects=True)
                continue

            # 2. Meta-Refresh prüfen
            meta_refresh = soup.find("meta", attrs={"http-equiv": re.compile(r"refresh", re.I)})
            if meta_refresh and "url=" in meta_refresh.get("content", "").lower():
                raw_url = re.split(r"url=", meta_refresh["content"], flags=re.I)[1].strip("'\" ")
                next_url = html.unescape(raw_url)
                next_url = urljoin(current_res.url, next_url)
                current_res = self._session.get(next_url, allow_redirects=True)
                continue

            break
        return current_res

    def login(self):
        try:
            # 1. Startseite aufrufen -> Einstiegs-Login-URL mit allen OAuth-Parametern
            init_res = self._session.get(f"https://{self.iserv_url}/iserv/", allow_redirects=True)
            login_url = init_res.url

            # 2. Login-Daten per POST senden
            login_data = {
                "_username": self.username,
                "_password": self._password,
                "_remember_me": "on"
            }

            login_response = self._session.post(
                login_url,
                data=login_data,
                headers={"Referer": login_url},
                allow_redirects=True
            )

            if "Anmeldung fehlgeschlagen!" in login_response.text:
                raise exceptions.AuthError("Login failed! Probably wrong username or password.")

            # 3. Allen Meta-Refresh- und OAuth-Callback-Schritten folgen
            self._follow_meta_and_links(login_response)

            # 4. Weboberfläche laden zur Bestätigung der Sitzung
            self._session.get(f"https://{self.iserv_url}/iserv/app/dashboard", allow_redirects=True)

            # Cookies für IServAPI-Felder registrieren
            cookies = self._session.cookies.get_dict()
            self._IServSAT = cookies.get("IServSAT")
            self._IServSATId = cookies.get("IServSATId")
            self._IServSession = (
                cookies.get("IServSession")
                or cookies.get("ISERV_SESSION")
                or cookies.get("PHPSESSID")
                or (list(cookies.values())[0] if cookies else "session_active")
            )

            # 5. Gegen Kalender-Endpunkt verifizieren
            test_res = self._session.get(
                f"https://{self.iserv_url}/iserv/calendar/api/upcoming",
                headers={"X-Requested-With": "XMLHttpRequest"}
            )

            if test_res.status_code == 401 or "/auth/login" in test_res.url:
                raise exceptions.AuthError("Authentication failed: API rejected session.")

            logging.info("Authentication successful and verified!")

        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(f"Error establishing connection: {e}")