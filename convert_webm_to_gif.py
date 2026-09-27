import imageio
from PIL import Image
import os

input_webm = "/config/Desktop/Session1/urbannest-concierge/videos/demo_video.webm"
output_gif = "/config/Desktop/Session1/urbannest-concierge/videos/demo.gif"

print(f"Reading {input_webm}...")
reader = imageio.get_reader(input_webm)
fps = reader.get_meta_data().get('fps', 10)

frames = []
# Subsample frames to keep GIF smooth and file size optimized (~5 fps)
step = max(1, int(fps / 5))

for i, frame in enumerate(reader):
    if i % step == 0:
        img = Image.fromarray(frame)
        # Resize to 960 width to keep crisp yet compact
        w, h = img.size
        new_w = 960
        new_h = int(h * (new_w / w))
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        frames.append(img)

print(f"Saving {len(frames)} frames to {output_gif}...")
frames[0].save(
    output_gif,
    save_all=True,
    append_images=frames[1:],
    optimize=True,
    duration=200, # 200ms per frame = 5fps
    loop=0
)

print(f"Done! Saved GIF size: {os.path.getsize(output_gif) / (1024*1024):.2f} MB")
