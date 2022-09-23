"""Helpers for the Tibber integration."""
import base64
import datetime
import json
import logging

import tibber

_LOGGER = logging.getLogger(__name__)


async def get_historic_data(
    tibber_home: tibber.TibberHome, tibber_controller: tibber.Tibber
):
    """Get historic data."""
    # pylint: disable=consider-using-f-string
    query = """
            {{
              viewer {{
                home(id: "{0}") {{
                  consumption(resolution: HOURLY, last: 744, before:"{1}") {{
                    nodes {{
                      consumption
                      cost
                      from
                      unitPrice
                    }}
                  }}
                }}
              }}
            }}
      """.format(
        tibber_home.home_id,
        base64.b64encode(datetime.datetime.now().isoformat().encode("ascii")).decode(),
    )

    if not (data := await tibber_controller.execute(query)):
        _LOGGER.error("Could not find the data.")
        return None
    data = data["viewer"]["home"]["consumption"]
    if data is None:
        return None
    return data["nodes"]


async def get_historic_production_data(
    tibber_home: tibber.TibberHome, tibber_controller: tibber.Tibber
):
    """Get historic data."""
    # pylint: disable=consider-using-f-string
    query = """
            {{
              viewer {{
                home(id: "{0}") {{
                  production(resolution: HOURLY, last: 744, before:"{1}") {{
                    nodes {{
                        from
                        profit
                    }}
                  }}
                }}
              }}
            }}
      """.format(
        tibber_home.home_id,
        base64.b64encode(datetime.datetime.now().isoformat().encode("ascii")).decode(),
    )

    if not (data := await tibber_controller.execute(query)):
        _LOGGER.error("Could not find the data.")
        return None
    data = data["viewer"]["home"]["production"]
    if data is None:
        return None
    return data["nodes"]


async def get_tibber_token(session, email: str, password: str):
    """Login to tibber."""
    post_args = {
        "headers": {
            "content-type": "application/json",
        },
        "data": json.dumps({"email": email, "password": password}),
    }
    resp = await session.post(
        "https://app.tibber.com/v1/login.credentials", **post_args
    )
    res = await resp.json()
    return res.get("token")


async def get_tibber_data(session, token: str):
    """Get tibber data."""
    post_args = {
        "headers": {"content-type": "application/json", "cookie": f"token={token}"},
        "data": json.dumps(
            {
                "variables": {},
                "query": "{\n  me {\n    homes {\n      id\n      address {\n"
                "        addressText\n      }\n      subscription {\n"
                "        priceRating {\n          hourly {\n"
                "            entries {\n              time\n"
                "              gridPrice\n            }\n"
                "          }\n        }\n      }\n    }\n  }\n}\n",
            }
        ),
    }
    resp = await session.post("https://app.tibber.com/v4/gql", **post_args)
    return await resp.json()


async def get_tibber_chargers(session, token: str, home_id: str):
    """Get tibber device data."""
    post_args = {
        "headers": {"content-type": "application/json", "cookie": f"token={token}"},
        "data": json.dumps(
            {
                "variables": {},
                "query": '{ me { home(id: "' + home_id + '"){ bubbles{ type id } } } }',
            }
        ),
    }

    resp = await session.post("https://app.tibber.com/v4/gql", **post_args)
    res = []
    for bubble in (await resp.json())["data"]["me"]["home"]["bubbles"]:
        if bubble["type"] == "ev-charger":
            res.append(bubble["id"])
    return res


async def get_tibber_chargers_data(
    session,
    token: str,
    home_id: str,
    charger_id: str,
):
    """Get tibber device data."""
    now = datetime.datetime.now()
    post_args = {
        "headers": {"content-type": "application/json", "cookie": f"token={token}"},
        "data": json.dumps(
            {
                "variables": {},
                "query": '{ me { home(id: "'
                + home_id
                + '") { evCharger( id: "'
                + charger_id
                + '" ) { name lastSeen  state { cableIsLocked isCharging permanentCableLock }} } } }',
            }
        ),
    }
    resp = await session.post("https://app.tibber.com/v4/gql", **post_args)
    meta_data = (await resp.json())["data"]["me"]["home"]["evCharger"]

    # pylint: disable=consider-using-f-string
    post_args = {
        "headers": {"content-type": "application/json", "cookie": f"token={token}"},
        "data": json.dumps(
            {
                "variables": {},
                "query": '{ me { home(id: "'
                + home_id
                + '") { evChargerConsumption( id: "'
                + charger_id
                + '" resolution: "DAILY" from: "'
                + str(now.year)
                + "-"
                + "{:02d}".format(now.month)
                + '-01T00:00:00+0200" ) { from consumption energyCost } } } }',
            }
        ),
    }
    resp = await session.post("https://app.tibber.com/v4/gql", **post_args)
    charger_consumption = (await resp.json())["data"]["me"]["home"][
        "evChargerConsumption"
    ]

    return {"meta_data": meta_data, "charger_consumption": charger_consumption}
