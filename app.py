import json
import os
import queue
import shutil
import subprocess
import threading
import sys
from datetime import datetime, timezone
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

IMAGE_EXTS = {'.jpg', '.jpeg', '.webp', '.heic', '.heif', '.png', '.tif', '.tiff'}
VIDEO_EXTS = {'.mp4', '.mov', '.m4v', '.3gp'}
MEDIA_EXTS = IMAGE_EXTS | VIDEO_EXTS


def sidecar_key(path: Path) -> str:
    name = path.name.lower()
    suffix = '.supplemental-metadata.json'
    base = name[:-len(suffix)] if name.endswith(suffix) else path.stem.lower()
    return Path(base).stem.lower()


def iso_exif(timestamp):
    if not timestamp:
        return None
    return datetime.fromtimestamp(int(timestamp), timezone.utc).strftime('%Y:%m:%d %H:%M:%S')


def ffmpeg_date(value):
    if not value:
        return None
    return datetime.strptime(value, '%Y:%m:%d %H:%M:%S').strftime('%Y-%m-%dT%H:%M:%SZ')


def run(cmd):
    return subprocess.run(cmd, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


class App:
    def __init__(self, root):
        self.root = root
        root.title('Media Metadata Merge')
        root.geometry('760x560')
        root.minsize(680, 480)
        self.q = queue.Queue()
        self.media_dir = tk.StringVar()
        self.json_dir = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.jpeg = tk.BooleanVar(value=False)
        self.same_date = tk.BooleanVar(value=True)
        self.build_ui()
        root.after(100, self.drain_log)

    def build_ui(self):
        pad = {'padx': 10, 'pady': 6}
        ttk.Label(self.root, text='Media Metadata Merge', font=('Segoe UI', 18, 'bold')).pack(anchor='w', **pad)
        ttk.Label(self.root, text='Merge Google Photos JSON sidecars into new image or video copies. Originals are never changed.', wraplength=700).pack(anchor='w', **pad)
        form = ttk.Frame(self.root)
        form.pack(fill='x', padx=10, pady=8)
        self.row(form, 0, 'Media folder', self.media_dir)
        self.row(form, 1, 'JSON folder', self.json_dir)
        self.row(form, 2, 'Output folder', self.output_dir)
        opts = ttk.LabelFrame(self.root, text='Options')
        opts.pack(fill='x', padx=10, pady=6)
        ttk.Checkbutton(opts, text='Convert images to JPEG', variable=self.jpeg).pack(anchor='w', padx=10, pady=5)
        ttk.Checkbutton(opts, text='Use capture date for common creation/modification fields', variable=self.same_date).pack(anchor='w', padx=10, pady=5)
        actions = ttk.Frame(self.root)
        actions.pack(fill='x', padx=10, pady=8)
        self.merge_btn = ttk.Button(actions, text='Merge Metadata', command=self.start)
        self.merge_btn.pack(side='left')
        ttk.Button(actions, text='Clear Log', command=self.clear_log).pack(side='left', padx=8)
        self.progress = ttk.Progressbar(actions, mode='indeterminate')
        self.progress.pack(side='right', fill='x', expand=True, padx=(20, 0))
        box = ttk.LabelFrame(self.root, text='Log')
        box.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        self.log = tk.Text(box, height=16, wrap='word', state='disabled', font=('Consolas', 9))
        self.log.pack(side='left', fill='both', expand=True)
        scroll = ttk.Scrollbar(box, command=self.log.yview)
        scroll.pack(side='right', fill='y')
        self.log.configure(yscrollcommand=scroll.set)

    def row(self, parent, r, label, variable):
        ttk.Label(parent, text=label, width=14).grid(row=r, column=0, sticky='w')
        ttk.Entry(parent, textvariable=variable).grid(row=r, column=1, sticky='ew', padx=6)
        ttk.Button(parent, text='Browse...', command=lambda v=variable: self.browse(v)).grid(row=r, column=2)
        parent.columnconfigure(1, weight=1)

    def browse(self, variable):
        chosen = filedialog.askdirectory()
        if chosen:
            variable.set(chosen)

    def log_msg(self, text):
        self.q.put(str(text))

    def drain_log(self):
        try:
            while True:
                msg = self.q.get_nowait()
                self.log.configure(state='normal')
                self.log.insert('end', msg + '\n')
                self.log.see('end')
                self.log.configure(state='disabled')
        except queue.Empty:
            pass
        self.root.after(100, self.drain_log)

    def clear_log(self):
        self.log.configure(state='normal')
        self.log.delete('1.0', 'end')
        self.log.configure(state='disabled')

    def start(self):
        media = Path(self.media_dir.get())
        metadata = Path(self.json_dir.get())
        output = Path(self.output_dir.get())
        if not media.is_dir() or not metadata.is_dir() or not output.is_dir():
            messagebox.showerror('Choose folders', 'Please select valid media, JSON, and output folders.')
            return
        self.merge_btn.configure(state='disabled')
        self.progress.start(10)
        threading.Thread(target=self.process, args=(media, metadata, output), daemon=True).start()

    def process(self, media_dir, json_dir, output_dir):
        try:
            tools = self.find_tools()
            json_map = {}
            for p in json_dir.rglob('*.json'):
                if p.name.lower().endswith('.supplemental-metadata.json'):
                    json_map[sidecar_key(p)] = p
            media_files = [p for p in media_dir.rglob('*') if p.is_file() and p.suffix.lower() in MEDIA_EXTS]
            if not media_files:
                self.log_msg('No supported media files found.')
            done = 0
            for src in media_files:
                meta = json_map.get(src.stem.lower())
                if not meta:
                    self.log_msg(f'SKIP: no matching JSON for {src.name}')
                    continue
                try:
                    out = self.merge_one(src, meta, output_dir, tools)
                    done += 1
                    self.log_msg(f'OK: {src.name} -> {out.name}')
                except Exception as exc:
                    self.log_msg(f'ERROR: {src.name}: {exc}')
            self.log_msg(f'Finished. {done} file(s) created. Originals were not modified.')
            self.root.after(0, lambda: messagebox.showinfo('Finished', f'{done} metadata-enriched file(s) created.'))
        except Exception as exc:
            self.log_msg('FAILED: ' + str(exc))
            self.root.after(0, lambda: messagebox.showerror('Merge failed', str(exc)))
        finally:
            self.root.after(0, self.finish)

    def finish(self):
        self.progress.stop()
        self.merge_btn.configure(state='normal')

    def find_tools(self):
        # Search both normal onedir builds and PyInstaller bundle folders.
        roots = [
            Path(__file__).resolve().parent,
            Path(sys.executable).resolve().parent,
            Path(getattr(sys, '_MEIPASS', '')),
            Path.cwd(),
        ]
        names = {}
        for wanted in ('ffmpeg.exe', 'exiftool.exe'):
            candidates = []
            for root in roots:
                if not root.exists():
                    continue
                candidates.extend(p for p in root.rglob('*') if p.is_file() and p.name.lower() in {wanted, 'exiftool(-k).exe'} and (wanted == 'exiftool.exe' or p.name.lower() == wanted))
            bundled = next((p for p in candidates if p.name.lower() == wanted), None)
            if bundled is None and wanted == 'exiftool.exe':
                bundled = next((p for p in candidates if p.name.lower() == 'exiftool(-k).exe'), None)
            names[wanted] = str(bundled) if bundled else wanted
        for name, cmd in names.items():
            try:
                run([cmd, '-version'])
            except Exception:
                searched = '\n'.join('  ' + str(root) for root in roots)
                raise RuntimeError(f'{name} was not found in the packaged application. Searched:\n{searched}\nPlease download the newest GitHub Actions artifact.')
        return names

    def merge_one(self, src, meta_path, output_dir, tools):
        data = json.loads(meta_path.read_text(encoding='utf-8-sig'))
        source_info = {}
        try:
            source_info = json.loads(run([tools['exiftool.exe'], '-j', '-G1', '-s', str(src)]).stdout)[0]
        except Exception:
            pass
        make = source_info.get('Make') or source_info.get('QuickTime:Make') or source_info.get('Keys:Make')
        model = source_info.get('Model') or source_info.get('QuickTime:Model') or source_info.get('Keys:Model')
        software = source_info.get('Software') or source_info.get('QuickTime:Software') or source_info.get('Keys:Software')
        taken = iso_exif(data.get('photoTakenTime', {}).get('timestamp'))
        created = iso_exif(data.get('creationTime', {}).get('timestamp'))
        title = data.get('title') or src.name
        geo = data.get('geoData') or {}
        valid_gps = any(abs(float(geo.get(k, 0) or 0)) > 0 for k in ('latitude', 'longitude'))
        ext = src.suffix.lower()
        out_ext = '.jpg' if self.jpeg and ext not in {'.jpg', '.jpeg'} and ext in IMAGE_EXTS else ext
        out = output_dir / (src.stem + '_metadata' + out_ext)
        output_dir.mkdir(parents=True, exist_ok=True)
        if ext in VIDEO_EXTS:
            cmd = [tools['ffmpeg.exe'], '-y', '-i', str(src), '-map', '0:0', '-map', '0:1?', '-c', 'copy', '-metadata', f'title={title}', '-metadata', f'comment=Google Photos metadata; device type={data.get("googlePhotosOrigin", {}).get("mobileUpload", {}).get("deviceType", "unknown")}; GPS present={valid_gps}']
            if ffmpeg_date(taken or created):
                cmd += ['-metadata', f'creation_time={ffmpeg_date(taken or created)}']
            run(cmd + [str(out)])
        elif self.jpeg and out_ext == '.jpg':
            run([tools['ffmpeg.exe'], '-y', '-i', str(src), '-q:v', '2', str(out)])
        else:
            shutil.copy2(src, out)
        tags = ['-Title=' + str(title), '-XMP-dc:Title=' + str(title)]
        if taken:
            tags += ['-DateTimeOriginal=' + taken]
        if self.same_date and taken:
            tags += ['-CreateDate=' + taken, '-ModifyDate=' + taken, '-XMP-xmp:CreateDate=' + taken + '+00:00', '-XMP-xmp:ModifyDate=' + taken + '+00:00', '-IPTC:DateCreated=' + taken[:10], '-IPTC:TimeCreated=' + taken[11:] + '+00:00', '-FileModifyDate=' + taken + '+00:00']
        elif created:
            tags += ['-CreateDate=' + created]
        if valid_gps:
            lat, lon = float(geo['latitude']), float(geo['longitude'])
            tags += [f'-GPSLatitude={abs(lat)}', f'-GPSLatitudeRef={"N" if lat >= 0 else "S"}', f'-GPSLongitude={abs(lon)}', f'-GPSLongitudeRef={"E" if lon >= 0 else "W"}']
            if geo.get('altitude') is not None:
                tags += [f'-GPSAltitude={geo["altitude"]}', '-GPSAltitudeRef=0']
        if make: tags += ['-Make=' + str(make)]
        if model: tags += ['-Model=' + str(model)]
        if software: tags += ['-Software=' + str(software)]
        run([tools['exiftool.exe'], '-overwrite_original'] + tags + [str(out)])
        if not out.exists() or out.stat().st_size == 0:
            raise RuntimeError('output was not created')
        return out


if __name__ == '__main__':
    root = tk.Tk()
    App(root)
    root.mainloop()
