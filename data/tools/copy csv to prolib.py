import shutil
import os

src = r'data\Artist.csv'
src2 = r'data\new artist to write in.csv'
dst_dir = r'E:\Project Library\Write library\资源库索引'
os.makedirs(dst_dir, exist_ok=True)
dst = os.path.join(dst_dir, r'Artist.csv')
dst2 = os.path.join(dst_dir, r'new artist to write in.csv')

shutil.copy2(src, dst)
print(f'Copied {src} to {dst}')
shutil.copy2(src2, dst2)
print(f'Copied {src2} to {dst2}')