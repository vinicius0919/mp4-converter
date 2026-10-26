import json
import os
import queue
import shutil
import subprocess
import threading
import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

FFMPEG = shutil.which('ffmpeg') or 'ffmpeg'
FFPROBE = shutil.which('ffprobe') or 'ffprobe'
VIDEO_SAFE = {'h264', 'hevc', 'av1', 'mpeg4'}
AUDIO_SAFE = {'aac', 'mp3', 'ac3'}
TEXT_SUBS = {'subrip', 'ass', 'ssa', 'webvtt', 'mov_text', 'text'}
LANG = {'por':'Português', 'pt':'Português', 'pob':'Português BR', 'jpn':'Japonês', 'eng':'Inglês', 'und':'Indefinido', 'spa':'Espanhol'}

class Converter:
    def __init__(self, root):
        self.root = root
        root.title('MP4 Converter PRO — Áudio e Legendas')
        root.geometry('950x730')
        root.configure(bg='#111827')
        self.events = queue.Queue()
        self.files = []
        self.info = None
        self.busy = False
        self.cancel = threading.Event()
        self.proc = None
        self.status = tk.StringVar(value='Aguardando arquivos')
        self.audio_choice = tk.StringVar()
        self.sub_choice = tk.StringVar(value='Nenhuma')
        self.sub_extra = tk.BooleanVar(value=False)
        self.subtitle_mode = tk.StringVar(value='Gravar permanentemente no vídeo (Hardsub)')
        self.setup_ui()
        root.after(80, self.drain)
        if not all(shutil.which(x) for x in ('ffmpeg','ffprobe')):
            self.write('⚠ FFmpeg ou FFprobe não está no PATH. Configure antes de converter.')
        else:
            self.write('✅ FFmpeg e FFprobe detectados. Sistema pronto.')

    def setup_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TLabel', background='#111827', foreground='#e5e7eb', font=('Segoe UI',10))
        style.configure('TFrame', background='#111827')
        style.configure('TButton', padding=8)
        style.configure('TCombobox', padding=6)
        tk.Label(self.root, text='MP4 Converter PRO', bg='#111827', fg='white', font=('Segoe UI',22,'bold')).pack(pady=(18,8))
        toolbar = ttk.Frame(self.root)
        toolbar.pack(fill='x', padx=20)
        ttk.Button(toolbar, text='Adicionar vídeos', command=self.add_files).pack(side='left', padx=4)
        ttk.Button(toolbar, text='Remover selecionado', command=self.remove_file).pack(side='left', padx=4)
        self.start_btn = ttk.Button(toolbar, text='▶ Converter fila', command=self.start)
        self.start_btn.pack(side='right', padx=4)
        self.stop_btn = ttk.Button(toolbar, text='■ Cancelar', command=self.stop, state='disabled')
        self.stop_btn.pack(side='right', padx=4)
        frame = ttk.Frame(self.root)
        frame.pack(fill='both', padx=20, pady=(12,6))
        self.listbox = tk.Listbox(frame, height=6, bg='#1f2937', fg='white', selectbackground='#2563eb', relief='flat', font=('Segoe UI',10))
        self.listbox.pack(fill='x')
        self.listbox.bind('<<ListboxSelect>>', self.on_select)
        opts = ttk.Frame(self.root)
        opts.pack(fill='x', padx=20, pady=10)
        ttk.Label(opts, text='Trilha de áudio').grid(row=0,column=0,sticky='w',pady=5)
        self.audio_combo = ttk.Combobox(opts, textvariable=self.audio_choice, state='readonly', width=76)
        self.audio_combo.grid(row=0,column=1,sticky='ew',padx=12,pady=5)
        ttk.Label(opts, text='Trilha de legenda').grid(row=1,column=0,sticky='w',pady=5)
        self.sub_combo = ttk.Combobox(opts, textvariable=self.sub_choice, state='readonly', width=76)
        self.sub_combo.grid(row=1,column=1,sticky='ew',padx=12,pady=5)
        ttk.Label(opts, text='Tratamento da legenda').grid(row=2,column=0,sticky='w',pady=5)
        self.mode_combo = ttk.Combobox(opts, textvariable=self.subtitle_mode, state='readonly', width=76, values=['Incluir no MP4 (legendas textuais)', 'Gravar permanentemente no vídeo (Hardsub)', 'Exportar legenda separada (formato original)'])
        self.mode_combo.grid(row=2,column=1,sticky='ew',padx=12,pady=5)
        ttk.Checkbutton(opts, text='Incluir também a legenda FORCED (se disponível)', variable=self.sub_extra, command=self.save_selection).grid(row=3,column=1,sticky='w',padx=12,pady=5)
        opts.columnconfigure(1,weight=1)
        ttk.Label(self.root, text='A seleção é individual por arquivo; clique em cada item da fila para configurar.').pack(anchor='w',padx=20)
        ttk.Label(self.root, textvariable=self.status).pack(anchor='w',padx=20,pady=(12,4))
        self.progress = ttk.Progressbar(self.root, mode='determinate', maximum=100)
        self.progress.pack(fill='x',padx=20,pady=(0,12))
        self.logbox = tk.Text(self.root, bg='#0b1220', fg='#d1d5db', insertbackground='white', font=('Consolas',10), relief='flat', wrap='word')
        self.logbox.pack(fill='both',expand=True,padx=20,pady=(0,18))

    def write(self, msg):
        self.logbox.insert('end', msg+'\n')
        self.logbox.see('end')

    def drain(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'log': self.write(value)
                elif kind == 'progress': self.progress['value'] = value
                elif kind == 'status': self.status.set(value)
                elif kind == 'done':
                    self.busy = False
                    self.start_btn.config(state='normal')
                    self.stop_btn.config(state='disabled')
                    self.status.set(value)
        except queue.Empty:
            pass
        self.root.after(80, self.drain)

    def probe(self, path):
        r = subprocess.run([FFPROBE,'-v','error','-show_streams','-show_format','-of','json',path], stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        if r.returncode: raise RuntimeError(r.stderr.decode('utf-8',errors='replace')[-1500:])
        data = json.loads(r.stdout.decode('utf-8',errors='replace'))
        streams = data.get('streams',[])
        return {'videos':[s for s in streams if s.get('codec_type')=='video' and not s.get('disposition',{}).get('attached_pic')],
                'audios':[s for s in streams if s.get('codec_type')=='audio'],
                'subs':[s for s in streams if s.get('codec_type')=='subtitle'],
                'duration':float(data.get('format',{}).get('duration') or 0)}

    def stream_label(self,s):
        tags=s.get('tags') or {}
        language=tags.get('language','und')
        name=tags.get('title','')
        channels=f" • {s.get('channels')} canais" if s.get('codec_type')=='audio' else ''
        return f"#{s['index']} • {LANG.get(language.lower(),language)} • {s.get('codec_name','?')}{channels}"+(f' • {name}' if name else '')

    def save_selection(self):
        i=self.selected_index()
        if i is None or i>=len(self.files): return
        item=self.files[i]
        a=self.audio_combo.current()
        s=self.sub_combo.current()
        if a>=0 and item['info']['audios']: item['audio']=a
        item['sub']=s-1 if s>=0 else -1
        item['mode']=self.subtitle_mode.get()
        item['extra']=self.sub_extra.get()

    def selected_index(self):
        selection=self.listbox.curselection()
        return selection[0] if selection else None

    def on_select(self,_=None):
        i=self.selected_index()
        if i is None: return
        item=self.files[i]
        info=item['info']
        self.audio_combo['values']=[self.stream_label(s) for s in info['audios']]
        self.sub_combo['values']=['Nenhuma']+[self.stream_label(s) for s in info['subs']]
        if info['audios']: self.audio_combo.current(min(item['audio'],len(info['audios'])-1))
        else: self.audio_choice.set('Nenhum áudio disponível')
        self.sub_combo.current(item['sub']+1)
        self.subtitle_mode.set(item['mode'])
        self.sub_extra.set(item.get('extra',False))
        self.audio_combo.bind('<<ComboboxSelected>>', lambda e:self.save_selection())
        self.sub_combo.bind('<<ComboboxSelected>>', lambda e:self.save_selection())
        self.mode_combo.bind('<<ComboboxSelected>>', lambda e:self.save_selection())

    def add_files(self):
        if self.busy: return
        paths=filedialog.askopenfilenames(filetypes=[('Vídeos','*.mkv *.mp4 *.avi *.mov *.webm'),('Todos','*.*')])
        for path in paths:
            if any(x['path']==path for x in self.files): continue
            try:
                info=self.probe(path)
                if not info['videos']: raise ValueError('Nenhuma trilha de vídeo encontrada')
                default_sub = next((i for i, sub in enumerate(info['subs']) if sub.get('codec_name') in {'ass','ssa','subrip','webvtt','text'} and 'FORCED' not in (sub.get('tags') or {}).get('title','').upper()), -1)
                self.files.append({'path':path,'info':info,'audio':0,'sub':default_sub,'mode':'Gravar permanentemente no vídeo (Hardsub)' if default_sub >= 0 else 'Incluir no MP4 (legendas textuais)','extra':False})
                self.listbox.insert('end',Path(path).name)
                self.write(f'📁 {Path(path).name}: {len(info["audios"])} áudio(s), {len(info["subs"])} legenda(s)')
                if default_sub >= 0: self.write('🔥 Padrão: Hardsub com ' + self.stream_label(info['subs'][default_sub]))
            except Exception as e: self.write(f'❌ Falha na análise de {Path(path).name}: {e}')
        if self.files and self.selected_index() is None:
            self.listbox.selection_set(0)
            self.on_select()

    def remove_file(self):
        if self.busy: return
        i=self.selected_index()
        if i is None:return
        self.files.pop(i)
        self.listbox.delete(i)
        if self.files:
            self.listbox.selection_set(min(i,len(self.files)-1))
            self.on_select()

    def stop(self):
        self.cancel.set()
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
        self.events.put(('log','⏹ Cancelamento solicitado.'))

    def start(self):
        if self.busy or not self.files:return
        self.save_selection()
        summary = []
        for item in self.files:
            sub = item['info']['subs'][item['sub']] if item['sub'] >= 0 else None
            summary.append(f"{Path(item['path']).name}\n  Modo: {item['mode']}\n  Legenda: {self.stream_label(sub) if sub else 'NENHUMA'}")
        if not messagebox.askyesno('Confirmar conversão', 'Confira as configurações antes de converter:\n\n' + '\n\n'.join(summary[:5]) + ('\n\n... outros arquivos' if len(summary)>5 else '') + '\n\nContinuar?'):
            return
        self.busy=True
        self.cancel.clear()
        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        threading.Thread(target=self.worker,daemon=True).start()

    def worker(self):
        ok=0
        total=len(self.files)
        for n,item in enumerate(list(self.files),1):
            if self.cancel.is_set():break
            self.events.put(('status',f'Convertendo {n}/{total}'))
            self.events.put(('progress',0))
            try:
                self.convert(item)
                ok+=1
            except Exception as e:
                self.events.put(('log',f'❌ {Path(item["path"]).name}: {e}'))
        self.events.put(('log',f'Fila finalizada: {ok}/{total} convertido(s).'))
        self.events.put(('done',f'Concluído: {ok}/{total}' if not self.cancel.is_set() else 'Cancelado'))

    def run_ffmpeg(self,cmd,duration,cwd=None):
        self.proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=cwd)
        # -progress pipe:1 gera linhas UTF-8/ASCII, evitando charmap do Windows.
        errors=[]
        def read_errors():
            for raw in self.proc.stderr:
                line=raw.decode('utf-8',errors='replace').strip()
                if line:errors.append(line)
                if len(errors)>35:errors.pop(0)
        t=threading.Thread(target=read_errors,daemon=True)
        t.start()
        for raw in self.proc.stdout:
            if self.cancel.is_set():
                self.proc.terminate()
                break
            line=raw.decode('utf-8',errors='replace').strip()
            if line.startswith('out_time='):
                try:
                    h,m,s=line.split('=',1)[1].split(':')
                    seconds=int(h)*3600+int(m)*60+float(s)
                    if duration>0:self.events.put(('progress',min(99.9,seconds/duration*100)))
                except (ValueError,IndexError):pass
        code=self.proc.wait()
        t.join(timeout=2)
        self.proc=None
        if self.cancel.is_set():raise RuntimeError('Conversão cancelada')
        if code:raise RuntimeError('FFmpeg falhou:\n'+'\n'.join(errors[-12:]))

    def convert(self,item):
        path=item['path']; info=item['info']
        name=Path(path).name
        output=Path(path).with_suffix('.mp4')
        if output.resolve()==Path(path).resolve(): output=Path(path).with_name(Path(path).stem+'_convertido.mp4')
        if output.exists():
            base=output.with_suffix(''); k=1
            while output.exists():
                output=Path(f'{base}_{k}.mp4');k+=1
        video=info['videos'][0]
        cmd=[FFMPEG,'-hide_banner','-nostdin','-y','-i',path,'-map',f'0:{video["index"]}']
        audio=None
        if info['audios']:
            audio=info['audios'][item['audio']]
            cmd+=['-map',f'0:{audio["index"]}']
        if item['mode'].startswith('Gravar') and item['sub'] < 0:
            raise RuntimeError('Selecione uma trilha de legenda para gravar na imagem.')
        hardburn = item['mode'].startswith('Gravar') and item['sub'] >= 0
        sub=None
        if item['sub']>=0:
            sub=info['subs'][item['sub']]
            if item['mode'].startswith('Incluir') and sub.get('codec_name') not in TEXT_SUBS:
                raise RuntimeError(f'Legenda {sub.get("codec_name")} é gráfica/incompatível com MP4. Selecione "Exportar legenda separada" ou outra trilha textual.')
            if item['mode'].startswith('Incluir'):cmd+=['-map',f'0:{sub["index"]}']
        subs_to_embed = [sub] if sub and item['mode'].startswith('Incluir') else []
        if subs_to_embed and item.get('extra'):
            for candidate in info['subs']:
                title=(candidate.get('tags') or {}).get('title','').upper()
                if candidate['index'] != sub['index'] and 'FORCED' in title and candidate.get('codec_name') in TEXT_SUBS:
                    cmd+=['-map',f'0:{candidate["index"]}']
                    subs_to_embed.append(candidate)
                    break
        cmd+=['-c:v','libx264' if hardburn or video.get('codec_name') not in VIDEO_SAFE else 'copy']
        if hardburn or video.get('codec_name') not in VIDEO_SAFE:cmd+=['-preset','medium','-crf','20']
        if audio:
            cmd+=['-c:a','copy' if audio.get('codec_name') in AUDIO_SAFE else 'aac']
            if audio.get('codec_name') not in AUDIO_SAFE:cmd+=['-b:a','192k']
        if subs_to_embed:
            cmd+=['-c:s','mov_text']
            for j,stream in enumerate(subs_to_embed):
                tags=stream.get('tags') or {}
                title=tags.get('title',f'Legenda {j+1}')
                cmd+= [f'-metadata:s:s:{j}',f'language={tags.get("language","por")}',f'-metadata:s:s:{j}',f'title={title}']
                forced=('FORCED' in title.upper() or bool(stream.get('disposition',{}).get('forced')))
                cmd += [f'-disposition:s:{j}', 'forced' if forced else ('default' if j==0 else '0')]
        else:cmd+=['-sn']
        cmd+=['-map_metadata','0','-map_chapters','0','-movflags','+faststart','-progress','pipe:1','-nostats',str(output)]
        self.events.put(('log',f'\n🎬 {name}'))
        self.events.put(('log',f'🎥 {video.get("codec_name")} | 🔊 {self.stream_label(audio) if audio else "sem áudio"}'))
        self.events.put(('log',f'💬 {self.stream_label(sub) if sub else "sem legendas"}'))
        try:
            if hardburn:
                if sub.get('codec_name') not in {'ass', 'ssa', 'subrip', 'webvtt', 'text'}:
                    raise RuntimeError('Hardsub nesta versão suporta legendas textuais (ASS, SSA, SRT, WebVTT).')
                # Extrair a legenda para um diretório temporário evita problemas com
                # caracteres especiais no caminho do Windows no filtro subtitles.
                with tempfile.TemporaryDirectory(prefix='mp4pro_') as temp:
                    subtitle_path = Path(temp) / 'legenda.ass'
                    extraction = subprocess.run(
                        [FFMPEG, '-hide_banner', '-nostdin', '-y', '-i', path,
                         '-map', f'0:{sub["index"]}', '-c:s', 'ass', str(subtitle_path)],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    if extraction.returncode:
                        raise RuntimeError('Falha ao extrair legenda ASS: ' + extraction.stderr.decode('utf-8', errors='replace')[-1200:])
                    # O FFmpeg executa com cwd=temp, portanto o filtro recebe
                    # apenas um nome simples, sem drive letter ou barras.
                    pos = cmd.index('-c:v')
                    cmd[pos:pos] = ['-vf', 'subtitles=legenda.ass']
                    self.events.put(('log', '🔥 Gravando legenda permanentemente (Hardsub / libx264).'))
                    self.run_ffmpeg(cmd, info['duration'], cwd=temp)
            else:
                self.run_ffmpeg(cmd,info['duration'])
            if sub and item['mode'].startswith('Exportar'):
                codec=sub.get('codec_name')
                extension={'subrip':'.srt','ass':'.ass','ssa':'.ssa','webvtt':'.vtt','hdmv_pgs_subtitle':'.sup','dvd_subtitle':'.sub'}.get(codec,'.mks')
                subtitle_output=output.with_suffix(extension)
                if subtitle_output.exists():subtitle_output=output.with_name(output.stem+'_legenda'+extension)
                # Matroska (.mks) é o fallback seguro para codecs de legenda desconhecidos.
                subcmd=[FFMPEG,'-hide_banner','-nostdin','-y','-i',path,'-map',f'0:{sub["index"]}','-c:s','copy',str(subtitle_output)]
                if extension in {'.sup','.sub'}:
                    # Alguns formatos gráficos não têm muxer direto; Matroska preserva a trilha.
                    subtitle_output=output.with_suffix('.mks')
                    subcmd=[FFMPEG,'-hide_banner','-nostdin','-y','-i',path,'-map',f'0:{sub["index"]}','-c:s','copy','-f','matroska',str(subtitle_output)]
                r=subprocess.run(subcmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                if r.returncode:self.events.put(('log','⚠ Vídeo pronto, mas a exportação da legenda falhou: '+r.stderr.decode('utf-8',errors='replace')[-500:]))
                else:self.events.put(('log',f'💬 Legenda exportada: {subtitle_output}'))
            self.events.put(('progress',100))
            self.events.put(('log',f'✅ Salvo: {output}'))
        except Exception:
            if output.exists():
                try:output.unlink()
                except OSError:pass
            raise

if __name__=='__main__':
    root=tk.Tk()
    Converter(root)
    root.mainloop()
