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
        if connexion.request.is_json:
            body = connexion.request.get_json()
            item, status = get_obj_or_404(Item, item_name=body["item_name"])
            if status == 200:
                item.update(item_count=item.item_count + int(body["item_count"]))
            else:
                item = Item.from_json(json.dumps(body))
                item.save()
            return Response(get_obj_or_404(Item, item_name=body["item_name"], to_json=True)[0],
                            mimetype="application/json",
                            status=200)

    if flask.request.method == "DELETE":
        return Item.objects(item_name=item_name).delete(), 200

    if flask.request.method == "PUT":
        if connexion.request.is_json:
            body = connexion.request.get_json()
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


@app.route("/place_order", methods=["GET", "POST"])
def place_order():
    if flask.request.method == "GET":
        items = [dict(item_name=i["item_name"], item_count=i["item_count"]) for i in
                 requests.get(url_for("show_products", _external=True)).json()]
        return render_template("order.html", items=items)


@app.route("/add_item", methods=["GET", "POST"])
def add_item():
    if flask.request.method == "GET":
        return render_template("item.html")
    elif flask.request.method == "POST":
        requests.post(url_for("show_products", _external=True), json=flask.request.form.to_dict())
        return flask.redirect(url_for("home"))


@app.route("/add_item", methods=["GET", "POST"])
def order():
    if flask.request.method == "GET":
        items = [dict(item_name=i["item_name"], item_count=i["item_count"], description=i["description"]) for i in
                 requests.get(url_for("show_products", _external=True)).json()]
        return render_template("order.html", items=items)


if __name__ == "__main__":
    app.run(host=host, debug=True, port=port)
