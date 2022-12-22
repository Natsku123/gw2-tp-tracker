import asyncio
import json
import os.path

import aiohttp
import logging
from pygw2.api import Api


logger = logging.getLogger("tp-tracker")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(
    logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s")
)
logger.addHandler(handler)


def price_to_gw2(price):
    """
    Convert numeric price to nice GW2 format

    :param price: int
    :return: string
    """
    c = price % 100
    s = price // 100 % 100
    g = price // 100 // 100
    return f"{g}g {s}s {c}c"


async def send_alert(webhook_url: str, data: dict):
    """
    Send alert to webhook

    :param webhook_url:
    :param data: json data
    :return:
    """
    async with aiohttp.ClientSession() as session:
        async with session.post(webhook_url, json=data) as req:
            logger.info(f"{webhook_url=}: {req.status}: {await req.text()}")


async def save_history(history: dict, history_file_path: str) -> None:
    """
    Save history into a JSON file

    :param history: dict
    :param history_file_path: str
    :return:
    """
    logger.debug("Saving history...")
    with open(history_file_path, "w", encoding="utf-8") as history_file:
        json.dump(history, history_file)


async def load_history(history_file_path: str) -> dict:
    """
    Load history from a JSON file

    :type history_file_path: str
    :return:
    """
    logger.debug("Loading history...")
    if not os.path.exists(history_file_path):
        logger.debug(f"Creating empty history file: {history_file_path}")
        with open(history_file_path, "w", encoding="utf-8") as history_file:
            json.dump({}, history_file)
    with open(history_file_path, encoding="utf-8") as history_file:
        history = json.load(history_file)

    return history


async def main():
    session = Api()
    history_file_path = "/data/history.json"
    while True:

        # Read config
        logger.debug("Loading config...")
        with open("config.json", encoding="utf-8") as config_file:
            config = json.load(config_file)

        if "history_file_path" in config:
            history_file_path = config["history_file_path"]

        if "loglevel" in config:
            if config["loglevel"] == "INFO":
                logger.setLevel(logging.INFO)
            elif config["loglevel"] == "DEBUG":
                logger.setLevel(logging.DEBUG)
            # TODO rest of levels

        # Read history
        nd_history = await load_history(history_file_path)

        if "trackers" in config:

            # Go through different trackers
            for tracker in config["trackers"]:
                hook_url = tracker["webhook_url"]
                items = [x["item_id"] for x in tracker["items"]]
                mentions = [x["mention"] for x in tracker["items"]]
                order_types = [x["order_type"] for x in tracker["items"]]
                lp_alert = [x["low_price_alert"] for x in tracker["items"]]
                nd_alert = [x["new_order_alert"] for x in tracker["items"]]

                # Get details and prices
                item_details = await session.items.get(*items)
                prices = await session.commerce.prices(*items)

                if not isinstance(prices, list):
                    prices: list = [prices]
                if not isinstance(item_details, list):
                    item_details: list = [item_details]

                detail_ids = [x.id for x in item_details]

                # Send update messages if necessary
                for price in prices:

                    # Map data
                    detail_index = detail_ids.index(price.id)
                    item_index = items.index(price.id)

                    # Get info from config
                    order_type = order_types[item_index]
                    lp = lp_alert[item_index]
                    nd = nd_alert[item_index]
                    mention = mentions[item_index]

                    if order_type == "buy":
                        price_info = price.buys
                    elif order_type == "sell":
                        price_info = price.sells
                    else:
                        price_info = None

                    # Check if prices have changed
                    if lp and lp > price_info.unit_price:
                        hook_data = {
                            "content": mention if mention else "",
                            "embeds": [
                                {
                                    "title": f"{order_type.capitalize()} order low price alert for *{item_details[detail_index].name}*",
                                    "type": "rich",
                                    "description": f"{order_type.capitalize()} order price dropped to **{price_to_gw2(price_info.unit_price)}**",
                                    "image": {"url": item_details[detail_index].icon},
                                    "provider": {
                                        "name": "GW2 Api",
                                        "url": f"https://api.guildwars2.com/v2/commerce/prices?ids={price.id}&lang=en",
                                    },
                                }
                            ],
                            # "allowed_mentions": "users"
                        }
                        await send_alert(hook_url, hook_data)

                    if nd and (
                        f"{price.id}-{order_type}" not in nd_history
                        or nd_history[f"{price.id}-{order_type}"]
                        != price_info.unit_price
                    ):
                        hook_data = {
                            "content": mention if mention else "",
                            "embeds": [
                                {
                                    "title": f"{order_type.capitalize()} order new price alert for *{item_details[detail_index].name}*",
                                    "type": "rich",
                                    "description": f"{order_type.capitalize()} order price changed to **{price_to_gw2(price_info.unit_price)}** from **{price_to_gw2(nd_history[f'{price.id}-{order_type}']) if f'{price.id}-{order_type}' in nd_history else '(no old price)'}**",
                                    "image": {"url": item_details[detail_index].icon},
                                    "provider": {
                                        "name": "GW2 Api",
                                        "url": f"https://api.guildwars2.com/v2/commerce/prices?ids={price.id}&lang=en",
                                    },
                                }
                            ],
                            # "allowed_mentions": "users"
                        }
                        nd_history[f"{price.id}-{order_type}"] = price_info.unit_price

                        await send_alert(hook_url, hook_data)

        await save_history(nd_history, history_file_path)
        await asyncio.sleep(config["interval"])


if __name__ == "__main__":
    # TODO nicer shutdown stuff for docker
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
