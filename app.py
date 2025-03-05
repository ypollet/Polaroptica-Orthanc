from flask import (
    Flask,
    render_template,
    jsonify,
    request,
    send_from_directory,
    send_file,
    abort,
)

from flask_cors import CORS, cross_origin

from base64 import encodebytes
import glob
import io
import os
from PIL import Image
import json
import numpy as np
import requests

from dotenv import load_dotenv

load_dotenv()

cwd = os.getcwd()

auth = None  # HTTPBasicAuth(os.environ.get("ORTHANC_USERNAME"), os.environ.get("ORTHANC_PASSWD"))
orthanc_server = os.environ.get("ORTHANC_SERVER")

# configuration
DEBUG = True

# instantiate the app
app = Flask(
    __name__,
    static_folder="frontend/dist/static",
    template_folder="frontend/dist",
    static_url_path="/static",
)
cors = CORS(app)
app.config["CORS_HEADERS"] = "Content-Type"
app.config.from_object(__name__)

# definitions
SITE = {"logo": "Polaroptica", "version": "1.0.0"}

OWNER = {
    "name": "Royal Belgian Institute of Natural Sciences",
}

# pass data to the frontend
site_data = {"site": SITE, "owner": OWNER}


# landing page
@app.route("/<id>")
def welcome(id):
    print(f"id : {id}")
    return render_template("index.html", **site_data)


def get_response_thumbnail(instance):
    byte_arr = requests.get(
        url=f"{orthanc_server}/instances/{instance}/attachments/thumbnail/data",
        auth=auth,
    ).content
    return byte_arr


def get_response_image(instance):
    byte_arr = requests.get(
        url=f"{orthanc_server}/instances/{instance}/content/7fe0-0010/1", auth=auth
    ).content
    return byte_arr


# send single image
@app.route("/<id>/<image_id>/full-image")
@cross_origin()
def image(id, image_id):
    try:
        image_binary = get_response_image(image_id)
        return send_file(
            io.BytesIO(image_binary), mimetype="image/jpeg", as_attachment=False
        )
    except Exception as error:
        print(error)


# send single image
@app.route("/<id>/<image_id>/thumbnail")
@cross_origin()
def thumbnail(id, image_id):
    try:
        image_binary = get_response_thumbnail(image_id)
        return send_file(
            io.BytesIO(image_binary), mimetype="image/jpeg", as_attachment=False
        )
    except Exception as error:
        print(error)


# send StackData
@app.route("/<id>/images")
@cross_origin()
def images(id):
    response = requests.get(
        url=f"{orthanc_server}/series/{id}/instances-tags?simplify", auth=auth
    )
    if not response.ok:
        abort(404)
    orthanc_dict: dict = json.loads(response.content)

    to_jsonify = {}
    encoded_images = []
    height = 0
    width = 0
    for instance, tags in orthanc_dict.items():
        try:
            width = tags["Columns"]
            height = tags["Rows"]
            encoded_images.append(
                {
                    "image": instance,
                    "name": instance,
                    "label": tags["UserContentLabel"],
                    "angle": float(tags["RotationAngle"]),
                }
            )
        except Exception as error:
            print(error)
            continue
    encoded_images.sort(key=lambda image: orthanc_dict[image["name"]]["RotationAngle"])
    to_jsonify["rotationImages"] = encoded_images
    to_jsonify["size"] = {"width": width, "height": height}

    return jsonify(to_jsonify)


@app.route("/<id>/position")
@cross_origin()
def compute_landmark(id):
    x = float(request.args.get("x"))
    y = float(request.args.get("y"))
    response = requests.get(
        url=f"{orthanc_server}/series/{id}/instances-tags?simplify", auth=auth
    )
    if not response.ok:
        abort(404)

    all_tags: dict = json.loads(response.content)
    key = next(iter(all_tags.keys()))
    tags = all_tags[key]
    pixel_spacing = [float(x) for x in tags["PixelSpacing"].split("\\")]
    position = {"x": x * pixel_spacing[0], "y": y * pixel_spacing[1]}
    return jsonify(position)


if __name__ == "__main__":
    app.run()
