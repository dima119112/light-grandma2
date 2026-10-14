from datetime import datetime, timedelta, tzinfo
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import json
import re
import requests
from bs4 import BeautifulSoup

SOURCE_URL = "https://www.ztoe.com.ua/unhooking-search.php"
QUEUE = "4"
SUBQUEUE = "4.1"
TIMEOUT_SECONDS = 15
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "schedule.json"


class EuropeKyivFallback(tzinfo):
    """EU rules for Europe/Kyiv when the IANA database is missing."""

    def tzname(self, dt):
        return "EEST" if self.utcoffset(dt) == timedelta(hours=3) else "EET"

    def utcoffset(self, dt):
        if dt is None:
            return None
        wall = dt.replace(tzinfo=None)
        if getattr(dt, "fold", 0):
            end = _last_sunday(wall.year, 10).replace(hour=4)
            if end - timedelta(hours=1) <= wall < end:
                return timedelta(hours=2)
        return timedelta(hours=3 if _wall_is_dst(wall) else 2)

    def dst(self, dt):
        offset = self.utcoffset(dt)
        if offset is None:
            return None
        return offset - timedelta(hours=2)

    def fromutc(self, dt):
        if dt.tzinfo is not self:
            raise ValueError("fromutc: dt.tzinfo is not self")
        utc = dt.replace(tzinfo=None)
        is_dst = _utc_is_dst(utc)
        local = utc + timedelta(hours=3 if is_dst else 2)
        fold = 0
        if not is_dst:
            end = _last_sunday(local.year, 10).replace(hour=4)
            if end - timedelta(hours=1) <= local < end:
                fold = 1
        return local.replace(tzinfo=self, fold=fold)


def _last_sunday(year, month):
    if month == 12:
        first_next = datetime(year + 1, 1, 1)
    else:
        first_next = datetime(year, month + 1, 1)
    last = first_next - timedelta(days=1)
    return last - timedelta(days=(last.weekday() + 1) % 7)


def _wall_is_dst(wall):
    start = _last_sunday(wall.year, 3).replace(hour=3)
    end = _last_sunday(wall.year, 10).replace(hour=4)
    return start <= wall < end


def _utc_is_dst(utc):
    start = _last_sunday(utc.year, 3).replace(hour=1)
    end = _last_sunday(utc.year, 10).replace(hour=1)
    return start <= utc < end


def kyiv_zone():
    try:
        return ZoneInfo("Europe/Kyiv")
    except ZoneInfoNotFoundError:
        return EuropeKyivFallback()


KYIV = kyiv_zone()


def classify_rgb(red, green, blue):
    if red >= 200 and green <= 120 and blue <= 120 and red > green + 40 and red > blue + 40:
        return "red"
    if red >= 230 and green >= 230 and blue >= 230:
        return "white"
    return None


def normalize_color(value):
    if not value:
        return None
    value = value.strip().lower().replace("!important", "").strip().strip("'\"")
    nested = re.search(r"background(?:-color)?\s*:\s*([^;]+)", value)
    if nested:
        return normalize_color(nested.group(1))
    if value == "red":
        return "red"
    if value == "white":
        return "white"
    rgb = re.fullmatch(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*[\d.]+)?\s*\)", value)
    if rgb:
        return classify_rgb(int(rgb.group(1)), int(rgb.group(2)), int(rgb.group(3)))
    hex_color = re.fullmatch(r"#([0-9a-f]{3,8})", value)
    if not hex_color:
        return None
    digits = hex_color.group(1)
    if len(digits) in (3, 4):
        red, green, blue = (int(digits[i] * 2, 16) for i in range(3))
    else:
        red, green, blue = int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16)
    return classify_rgb(red, green, blue)


def element_color(el):
    if el.has_attr("bgcolor"):
        color = normalize_color(el.get("bgcolor"))
        if color:
            return color
    color = normalize_color(el.get("style", ""))
    if color:
        return color
    for child in el.find_all(True):
        if child.has_attr("bgcolor"):
            color = normalize_color(child.get("bgcolor"))
            if color:
                return color
        color = normalize_color(child.get("style", ""))
        if color:
            return color
    return None


def parse_update_time(soup):
    text = soup.get_text(" ", strip=True)
    match = re.search(
        r"Дата оновлення інформації\s*[-:–]?\s*(\d{1,2}:\d{2})\s+(\d{1,2}\.\d{1,2}\.\d{4})",
        text,
        re.I,
    )
    return f"{match.group(2)} о {match.group(1)}" if match else None


def parse_schedule_date(soup, now):
    for el in soup.find_all(attrs={"colspan": True}):
        if str(el.get("colspan")) != "48":
            continue
        match = re.search(r"(\d{1,2}\.\d{1,2}\.\d{4})", el.get_text(" ", strip=True))
        if match:
            return match.group(1)
    updated = parse_update_time(soup)
    if updated:
        match = re.search(r"(\d{1,2}\.\d{1,2}\.\d{4})", updated)
        if match:
            return match.group(1)
    return now.strftime("%d.%m.%Y")


def half_hour_cells(row):
    cells = row.find_all(["td", "th"], recursive=False)
    if not cells:
        cells = row.find_all(["td", "th"])
    colored = []
    for cell in cells:
        label = " ".join(cell.stripped_strings).strip()
        if re.fullmatch(r"\d+(?:\.\d+)?", label):
            continue
        if element_color(cell) is None:
            continue
        colored.append(cell)
    if len(colored) >= 48:
        return colored[:48]
    if len(cells) >= 48:
        return cells[-48:]
    return colored


def parse_schedule():
    response = requests.get(
        SOURCE_URL,
        timeout=TIMEOUT_SECONDS,
        headers={"User-Agent": "Mozilla/5.0 (compatible; PowerScheduleHelper/1.0)"},
    )
    response.raise_for_status()
    encoding = (response.encoding or "").lower()
    if encoding in {"", "iso-8859-1", "latin-1", "ascii"}:
        response.encoding = "cp1251"
    soup = BeautifulSoup(response.text, "html.parser")
    updated = parse_update_time(soup)

    target_row = None
    for row in soup.find_all("tr"):
        row_text = " ".join(row.stripped_strings)
        if not re.search(r"\b4\.1\b", row_text):
            continue
        if len(row.find_all(["td", "th"], recursive=False)) >= 48:
            target_row = row
            break
    if target_row is None:
        raise ValueError("Не вдалося знайти рядок підчерги 4.1 на офіційному сайті.")

    slots = []
    for index, cell in enumerate(half_hour_cells(target_row)[:48]):
        color = element_color(cell)
        start_minutes = index * 30
        end_minutes = start_minutes + 30
        start = f"{start_minutes // 60:02d}:{start_minutes % 60:02d}"
        end = "24:00" if end_minutes == 1440 else f"{end_minutes // 60:02d}:{end_minutes % 60:02d}"
        if color == "red":
            status = "off"
        elif color == "white":
            status = "on"
        else:
            status = "unknown"
        slots.append({"start": start, "end": end, "status": status})

    if len(slots) != 48:
        raise ValueError(f"На сторінці знайдено {len(slots)} часових інтервалів замість 48.")
    if all(slot["status"] == "unknown" for slot in slots):
        raise ValueError("Знайдено таблицю, але не вдалося розпізнати кольори графіка.")

    periods = []
    for slot in slots:
        if periods and periods[-1]["status"] == slot["status"] and periods[-1]["end"] == slot["start"]:
            periods[-1]["end"] = slot["end"]
        else:
            periods.append(dict(slot))

    now = datetime.now(KYIV)
    now_minutes = now.hour * 60 + now.minute
    current_slot = slots[min(now_minutes // 30, 47)]
    next_change = None
    current_status = current_slot["status"]
    for slot in slots:
        start_minutes = int(slot["start"][:2]) * 60 + int(slot["start"][3:])
        if start_minutes > now_minutes and slot["status"] != current_status:
            next_change = {"time": slot["start"], "status": slot["status"]}
            break

    schedule_date = parse_schedule_date(soup, now)
    return {
        "queue": QUEUE,
        "subqueue": SUBQUEUE,
        "date": schedule_date,
        "updated": updated,
        "currentStatus": current_status,
        "nextChange": next_change,
        "periods": periods,
        "sourceUrl": SOURCE_URL,
        "checkedAt": now.strftime("%H:%M"),
        "isToday": schedule_date == now.strftime("%d.%m.%Y"),
    }


def main():
    data = parse_schedule()
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT.name}: {data['date']} {data['currentStatus']} checked {data['checkedAt']}")


if __name__ == "__main__":
    main()