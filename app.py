import base64
import json
from datetime import datetime

import connexion
import flask
import mongoengine
import requests
from flask import Response, render_template, url_for

from Models.Item import Item
from Models.order_details import Order

app = flask.Flask(__name__)
host = "localhost"
port = 8080


@app.template_filter()
def format_date(value):
    value = str(value)
    value = float(f"{value[:10]}.{value[10:]}")
    return datetime.fromtimestamp(value).strftime("%A, %B %d, %Y %I:%M:%S")


@app.template_filter()
def get_image_bytes(value):
    return base64.b64encode(Item.objects.get(pk=value).item_image.thumbnail.read()).decode("utf-8")


def get_obj_or_404(klass, *args, **kwargs):
    kwargs["to_json"] = kwargs.get("to_json", False)
    to_json = kwargs.get("to_json")
    kwargs.pop("to_json")
    try:
        if to_json:
            return klass.objects.get(*args, **kwargs).to_json(), 200
        else:
            return klass.objects.get(*args, **kwargs), 200

    except (mongoengine.errors.DoesNotExist, mongoengine.errors.ValidationError):
        return "", 404


@app.route("/items/", defaults={"item_name": None}, methods=["GET", "POST", "PUT", "DELETE"])
@app.route("/items/<string:item_name>", methods=["GET", "POST", "PUT", "DELETE"])
def show_products(item_name: str = None):
    if flask.request.method == "GET":
        return Response(Item.objects().to_json(), mimetype="application/json", status=200)
    if flask.request.method == "POST":
        files = flask.request.files
        body = flask.request.form
        item, status = get_obj_or_404(Item, item_name=body["item_name"])
        if status == 200:
            item.update(item_count=item.item_count + int(body["item_count"]))
        else:
            item = Item.from_json(json.dumps(body))
            item.item_image = files["item_image"]
            item.save()
        return Response(get_obj_or_404(Item, item_name=body["item_name"], to_json=True)[0],
                        mimetype="application/json",
                        status=200)

    if flask.request.method == "DELETE":
        Item.objects(item_name=item_name).delete()
        return Response(status=200)

    if flask.request.method == "PUT":
        body = flask.request.form
        item, status = get_obj_or_404(Item, item_name=item_name)
        if status == 200:
            item.update(**body)
            item, status = get_obj_or_404(Item, item_name=item_name, to_json=True)
        return Response(item, mimetype="application/json", status=status)


@app.route("/order/", defaults={"order_id": None}, methods=["POST", "GET"])
@app.route("/order/<string:order_id>", methods=["GET"])
def order_item(order_id: str = None):
    if flask.request.method == "GET":
        if order_id:
            item, status = get_obj_or_404(Order, pk=order_id, to_json=True)
        else:
            item, status = Order.objects.all().to_json(), 200
        return Response(item, status=status)
    if flask.request.method == "POST":
        if connexion.request.is_json:
            body = connexion.request.get_json()
            cost, cats, missing, items = 0, list(), list(), list()
            for item in body['items']:
                try:
                    _item = Item.objects.get(item_name=item["item_name"])
                    if _item.item_count >= item["quantity"] and _item.item_count > 0:
                        _item.update(item_count=_item.item_count - item["quantity"])
                        cost += item["quantity"] * _item.item_price
                        cats.append(_item.category)
                        items.append(item)
                    else:
                        missing.append(item)
                except mongoengine.errors.DoesNotExist:
                    missing.append(item)
            order = Order(buyer_name=body["buyer_name"],
                          items=items,
                          category=cats,
                          amount=cost,
                          order_status="Order Placed",
                          address=body["address"],
                          missing_items=missing)
            order.save()
            return Response(order.to_json(), content_type="application/json", status=200)


@app.route("/home", methods=["GET"])
def home():
    return render_template("home.html", items=requests.get(url_for("show_products", _external=True)).json(),
                           orders=requests.get(url_for("order_item", _external=True)).json())


@app.route("/add_item", defaults={"item_id": None}, methods=["GET", "POST"])
@app.route("/update/item/<string:item_id>", methods=["GET"])
@app.route("/delete/item/<string:item_id>", methods=["GET"])
def add_item(item_id):
    if flask.request.method == "GET":
        if item_id and "update" in flask.request.full_path:
            return render_template("item.html", item=Item.objects.get(pk=item_id).to_json())
        elif item_id and "delete" in flask.request.full_path:
            requests.delete(url_for("show_products", _external=True) + item_id)
            return flask.redirect(url_for("home"))
        return render_template("item.html")
    elif flask.request.method == "POST":
        args = [url_for("show_products", _external=True)]
        kwargs = dict(data=flask.request.form.to_dict())
        if flask.request.files:
            requester = requests.post
            kwargs.update({"files": {"item_image": flask.request.files["item_image"]}})
        elif flask.request.form.get("hidden", False):
            requester = requests.put
            kwargs["data"].pop("hidden")
            args[0] += kwargs["data"]["item_name"]
        else:
            requester = requests.post

        requester(*args, **kwargs)
        return flask.redirect(url_for("home"))


@app.route("/place_order", methods=["GET", "POST"])
def place_order():
    if flask.request.method == "GET":
        items = [dict(item_name=i["item_name"], item_count=i["item_count"], description=i["description"],
                      _id=i["_id"]["$oid"]) for i in
                 requests.get(url_for("show_products", _external=True)).json()]
        return render_template("order.html", items=items)
    elif flask.request.method == "POST":
        body = flask.request.form.to_dict()
        parsed_body = dict(items=[])
        for k, v in body.items():
            if "item--" in k and v:
                parsed_body["items"].append(dict(item_name=k.split("item--")[-1], quantity=int(v)))
            else:
                parsed_body.update({k: v})
        if len(parsed_body["items"]) < 1:
            return render_template("order.html", message="No Item selected. Please select an item and try again")
        else:
            requests.post(url_for("order_item", _external=True), json=parsed_body)
        return flask.redirect(url_for("home"))


if __name__ == "__main__":
    app.run(host=host, debug=True, port=port)
