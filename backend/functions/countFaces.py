# aws.run("countFaces", "door.jpg") -> how many faces are in a saved image.
#
# An example of the bottom level: this function calls Amazon Rekognition itself,
# so it works on aws only. Permissions are in settings.json "functions".
# It only counts faces (detection); it does not tell who they are.
import boto3


def run(input, context):
    if context["destination"] != "aws":
        return "countFaces only works on aws (it uses Amazon Rekognition)."
    res = boto3.client("rekognition").detect_faces(
        Image={"S3Object": {"Bucket": context["bucket"], "Name": f"saved/{context['device']}/{input}"}}
    )
    return str(len(res["FaceDetails"]))
