import asyncio
import json
import aiohttp
import logging
from pygw2.api import Api


logger = logging.getLogger('tp-tracker')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(
    logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s')
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


async def main():
    session = Api()
    nd_history = {}
    while True:

        # Read config
        with open('config.json') as config_file:
            config = json.load(config_file)

        if 'trackers' in config:

            # Go through different trackers
            for tracker in config['trackers']:
                hook_url = tracker['webhook_url']
                items = [x['item_id'] for x in tracker['items']]
                mentions = [x['mention'] for x in tracker['items']]
                order_types = [x['order_type'] for x in tracker['items']]
                lp_alert = [x['low_price_alert'] for x in tracker['items']]
                nd_alert = [x['new_order_alert'] for x in tracker['items']]

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
                                    "image": {
                                        "url": item_details[detail_index].icon
                                    },
                                    "provider": {
                                        "name": "GW2 Api",
                                        "url": f"https://api.guildwars2.com/v2/commerce/prices?ids={price.id}&lang=en"
                                    }
                                }
                            ],
                            #"allowed_mentions": "users"
                        }
                        await send_alert(hook_url, hook_data)

                    if nd and (f"{price.id}-{order_type}" not in nd_history or nd_history[f"{price.id}-{order_type}"] != price_info.unit_price):
                        hook_data = {
                            "content": mention if mention else "",
                            "embeds": [
                                {
                                    "title": f"{order_type.capitalize()} order new price alert for *{item_details[detail_index].name}*",
                                    "type": "rich",
                                    "description": f"{order_type.capitalize()} order price changed to **{price_to_gw2(price_info.unit_price)}** from **{price_to_gw2(nd_history[f'{price.id}-{order_type}']) if f'{price.id}-{order_type}' in nd_history else '(no old price)'}**",
                                    "image": {
                                        "url": item_details[detail_index].icon
                                    },
                                    "provider": {
                                        "name": "GW2 Api",
                                        "url": f"https://api.guildwars2.com/v2/commerce/prices?ids={price.id}&lang=en"
                                    }
                                }
                            ],
                            #"allowed_mentions": "users"
                        }
                        nd_history[f"{price.id}-{order_type}"] = price_info.unit_price

                        await send_alert(hook_url, hook_data)

        await asyncio.sleep(60*5)    # Sleep 5 minutes


if __name__ == '__main__':
    asyncio.run(main())
