# aws.run("faceBoxes", "e8/00.jpg") -> where the faces are, as "x y w h;" in pixels
# of a 640x480 image. Used by the evaluation (evaluation/e8_images) to score
# Amazon Rekognition against the same ground truth as the on-device detector.
import boto3

WIDTH, HEIGHT = 640, 480


def run(input, context):
    if context["destination"] != "aws":
        return "faceBoxes only works on aws (it uses Amazon Rekognition)."
    res = boto3.client("rekognition").detect_faces(
        Image={"S3Object": {"Bucket": context["bucket"], "Name": f"saved/{context['device']}/{input}"}}
    )
    boxes = []
    for face in res["FaceDetails"]:
        b = face["BoundingBox"]
        boxes.append(f"{round(b['Left'] * WIDTH)} {round(b['Top'] * HEIGHT)} "
                     f"{round(b['Width'] * WIDTH)} {round(b['Height'] * HEIGHT)}")
    return ";".join(boxes)
