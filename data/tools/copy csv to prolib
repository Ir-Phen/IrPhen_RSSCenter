import shutil
import os

src = r'data\Artist.csv'
dst_dir = r'E:\Project Library\Write library\资源库索引'
os.makedirs(dst_dir, exist_ok=True)
dst = os.path.join(dst_dir, 'Artist.csv')

shutil.copy2(src, dst)
print(f'Copied {src} to {dst}')