import os
import json
import requests

BASE_URL = "https://yelp-pipeline-1.onrender.com"

def call_search_image(
    image_path: str,
    user_query: str,
    location: str = "College Park, Maryland",
    date: str = "12/11/2025",
    time: str = "8pm",
    save_to_file: bool = False,
    out_json_path: str = "search_results.json"
):
    url = f"{BASE_URL}/search-image"

    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    with open(image_path, "rb") as f:
        files = {
            "image": (os.path.basename(image_path), f, "image/jpeg")
        }
        data = {
            "user_query": user_query,
            "Location": location,
            "Date": date,
            "Time": time,
            "save_to_file": str(save_to_file).lower()
        }

        r = requests.post(url, files=files, data=data, timeout=120)
        r.raise_for_status()
        result = r.json()

    with open(out_json_path, "w", encoding="utf-8") as fp:
        json.dump(result, fp, ensure_ascii=False, indent=2)

    return result


def call_search_caption(
    caption: str,
    user_query: str,
    location: str = "College Park, Maryland",
    date: str = "12/11/2025",
    time: str = "8pm",
    save_to_file: bool = False,
    out_json_path: str = "search_results.json"
):
    url = f"{BASE_URL}/search-caption"
    data = {
        "caption": caption,
        "user_query": user_query,
        "Location": location,
        "Date": date,
        "Time": time,
        "save_to_file": str(save_to_file).lower()
    }

    r = requests.post(url, data=data, timeout=120)
    r.raise_for_status()
    result = r.json()

    with open(out_json_path, "w", encoding="utf-8") as fp:
        json.dump(result, fp, ensure_ascii=False, indent=2)

    return result


def main():
    print("Choose mode:")
    print("1) Image upload")
    print("2) Caption only")
    mode = input("Enter 1 or 2: ").strip()

    if mode == "1":
        image_path = input("Enter local image path: ").strip()
        user_query = input("Describe what you want to find: ").strip()
        location = input("Location (press Enter for default): ").strip() or "College Park, Maryland"
        date = input("Date (press Enter for default): ").strip() or "12/11/2025"
        time = input("Time (press Enter for default): ").strip() or "8pm"

        res = call_search_image(
            image_path=image_path,
            user_query=user_query,
            location=location,
            date=date,
            time=time,
            save_to_file=False
        )

    elif mode == "2":
        caption = input("Paste image caption: ").strip()
        user_query = input("Describe what you want to find: ").strip()
        location = input("Location (press Enter for default): ").strip() or "College Park, Maryland"
        date = input("Date (press Enter for default): ").strip() or "12/11/2025"
        time = input("Time (press Enter for default): ").strip() or "8pm"

        res = call_search_caption(
            caption=caption,
            user_query=user_query,
            location=location,
            date=date,
            time=time,
            save_to_file=False
        )
    else:
        raise ValueError("Invalid mode")

    print("\nTop-level response keys:", res.keys())
    print("Query used:", res.get("query"))
    print("Businesses returned:", len(res.get("businesses", [])))
    print("\nSaved full response to search_results.json")


if __name__ == "__main__":
    main()