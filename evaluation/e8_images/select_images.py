"""Select WIDER FACE validation images for the on-device vs cloud face-count test.

The images are not stored in this repository (WIDER FACE is CC BY-NC-ND 4.0 and
shows people); this script records which ones were used and rebuilds them.

Usage:
  python3 select_images.py WIDER_DIR OUT_DIR [--n 40] [--seed 1] [--min-face 32]

WIDER_DIR holds WIDER_val/images/ and wider_face_split/ from the official release.
Rules, fixed on 2026-10-02 before any detector was run:
  - each image is scaled to fit 640x480 (the camera's frame) keeping its aspect
    ratio, padded with black to 640x480, and saved as JPEG at a quality whose file
    sizes match the camera's photos (15-23 KB);
  - an image qualifies if it has 1-5 valid faces (invalid flag 0) and every valid
    face has its shorter side at least MIN_FACE pixels after scaling, so that no
    face is too small to call either way;
  - images are drawn at random with a fixed seed, the same number for each face
    count from 1 to 5.
  - with --coco, NO_FACE images without any "person" annotation are drawn from
    COCO val2017 with the same seed and processed the same way (0 faces).
Writes OUT_DIR/images/NN.jpg and OUT_DIR/selection.csv (id, source, faces, boxes
as x y w h in the 640x480 frame).
"""
import argparse
import csv
import json
import os
import random
import urllib.request

from PIL import Image

MAX_FACES = 5
FRAME = (640, 480)


def read_annotations(path):
    with open(path) as f:
        lines = [line.strip() for line in f]
    i, items = 0, []
    while i < len(lines):
        name = lines[i]
        count = int(lines[i + 1])
        boxes = []
        for line in lines[i + 2 : i + 2 + max(count, 1)]:
            v = [int(x) for x in line.split()]
            if count and v[7] == 0:  # x y w h blur expression illumination invalid occlusion pose
                boxes.append(v[:4])
        items.append((name, boxes))
        i += 2 + max(count, 1)
    return items


def to_frame(path, out, quality):
    with Image.open(path) as im:
        scale = min(FRAME[0] / im.width, FRAME[1] / im.height)
        im = im.convert("RGB").resize((round(im.width * scale), round(im.height * scale)))
        frame = Image.new("RGB", FRAME)
        frame.paste(im, ((FRAME[0] - im.width) // 2, (FRAME[1] - im.height) // 2))
        frame.save(out, quality=quality)


def coco_without_people(ann_path, cache, count, rng):
    ann = json.load(open(ann_path))
    people = {a["image_id"] for a in ann["annotations"] if a["category_id"] == 1}
    files = sorted(i["file_name"] for i in ann["images"] if i["id"] not in people)
    chosen = rng.sample(files, count)
    os.makedirs(cache, exist_ok=True)
    for name in chosen:
        path = os.path.join(cache, name)
        if not os.path.exists(path):
            urllib.request.urlretrieve("http://images.cocodataset.org/val2017/" + name, path)
    return [os.path.join(cache, name) for name in chosen]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("wider")
    p.add_argument("out")
    p.add_argument("--n", type=int, default=40)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--min-face", type=int, default=32)
    p.add_argument("--coco", help="COCO annotations/instances_val2017.json")
    p.add_argument("--no-face", type=int, default=10)
    p.add_argument("--quality", type=int, default=25)  # 11-27 KB, median 18 KB, like the camera (15-23 KB)
    a = p.parse_args()

    items = read_annotations(os.path.join(a.wider, "wider_face_split", "wider_face_val_bbx_gt.txt"))
    by_count = {k: [] for k in range(1, MAX_FACES + 1)}
    for name, boxes in items:
        if not 1 <= len(boxes) <= MAX_FACES:
            continue
        with Image.open(os.path.join(a.wider, "WIDER_val", "images", name)) as im:
            scale = min(FRAME[0] / im.width, FRAME[1] / im.height)
            dx, dy = (FRAME[0] - round(im.width * scale)) // 2, (FRAME[1] - round(im.height * scale)) // 2
        if all(min(w, h) * scale >= a.min_face for _, _, w, h in boxes):
            scaled = [[round(x * scale) + dx, round(y * scale) + dy, round(w * scale), round(h * scale)]
                      for x, y, w, h in boxes]
            by_count[len(boxes)].append((name, scaled))

    rng = random.Random(a.seed)
    per = a.n // MAX_FACES
    chosen = []
    for k in range(1, MAX_FACES + 1):
        pool = sorted(by_count[k])
        chosen += rng.sample(pool, min(per, len(pool)))

    os.makedirs(os.path.join(a.out, "images"), exist_ok=True)
    with open(os.path.join(a.out, "selection.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "source", "faces", "boxes"])
        for n, (name, boxes) in enumerate(chosen):
            to_frame(os.path.join(a.wider, "WIDER_val", "images", name),
                     os.path.join(a.out, "images", f"{n:02d}.jpg"), a.quality)
            w.writerow([f"{n:02d}", name, len(boxes), ";".join(" ".join(map(str, b)) for b in boxes)])
        if a.coco:
            cache = os.path.join(os.path.dirname(a.coco), "..", "val2017")
            for n, path in enumerate(coco_without_people(a.coco, cache, a.no_face, rng), start=len(chosen)):
                to_frame(path, os.path.join(a.out, "images", f"{n:02d}.jpg"), a.quality)
                w.writerow([f"{n:02d}", "coco/val2017/" + os.path.basename(path), 0, ""])
    print({k: len(v) for k, v in by_count.items()}, "->", len(chosen), "images")


if __name__ == "__main__":
    main()
