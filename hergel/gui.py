import os
import base64
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from .event_catalog import load_catalog
from .window_style import style_title_bar
from .updater import check_update, download_update, launch_installer
from .version import VERSION
from .game import launch_game, prepare_game
from .pack import installed_game
from .microsoft_auth import get_client_id, sign_in, restore_session, sign_out
from .settings import load_settings, save_settings, ram_mb
from .minecraft_profile import render_placeholder_bust

DEFAULT_ROOT = (Path(os.environ['LOCALAPPDATA']) / 'HergelLauncher' / 'instances'
                if sys.platform == 'win32' and os.environ.get('LOCALAPPDATA')
                else Path.home() / '.local' / 'share' / 'HergelLauncher' / 'instances')
BG = '#100e1b'
SIDEBAR = '#171120'
PANEL = '#211a35'
PANEL_LIGHT = '#2b2243'
PURPLE = '#8a5cf6'
LAVENDER = '#c6a9ff'
TEXT = '#f5efff'
MUTED = '#a69cbb'
BORDER = '#392f53'
FONT = 'Segoe UI'
ASSETS = Path(__file__).parent.parent / 'assets'


def open_folder(folder):
    if sys.platform == 'win32':
        os.startfile(folder)
    elif sys.platform == 'darwin':
        subprocess.Popen(['open', str(folder)])
    else:
        subprocess.Popen(['xdg-open', str(folder)])


def label(parent, text, size=11, color=TEXT, weight='normal', bg=None, **kwargs):
    return tk.Label(parent, text=text if 'textvariable' not in kwargs else None, font=(FONT, size, weight), fg=color,
                    bg=bg or parent['bg'], **kwargs)


def button(parent, text, command, primary=False, **kwargs):
    return tk.Button(parent, text=text, command=command, font=(FONT, 10, 'bold'),
                     fg=TEXT, bg=PURPLE if primary else PANEL_LIGHT,
                     activebackground='#a77dff' if primary else BORDER,
                     activeforeground=TEXT, relief='flat', cursor='hand2',
                     padx=kwargs.pop('padx', 18), pady=kwargs.pop('pady', 10), borderwidth=0, **kwargs)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Hergel Launcher')
        self.geometry('1100x720')
        self.minsize(790, 570)
        self.configure(bg=BG)
        self.events = queue.Queue()
        self.packs = []
        self.selected_index = 0
        preferences = load_settings()
        self.source = tk.StringVar(value=str(Path(__file__).parent.parent / 'examples' / 'catalog.json'))
        self.memory_gb = tk.IntVar(value=preferences.get('ram_gb', 4))
        self.root_path = tk.StringVar(value=str(DEFAULT_ROOT))
        self.status = tk.StringVar(value='Preparando modalidades...')
        self.microsoft_account = None
        self.ready_game = None
        self.install_busy = False
        self.progress_stage = ''
        self.progress_current = 0
        self.progress_total = 0
        self.account_busy = False
        self.launcher_update = None
        self.update_busy = False
        self.update_check_busy = False
        self.update_required = False
        self.gradient_frame = 0
        self.red_frame = 0
        self.home_animation_enabled = True
        self.pack_animation_enabled = True
        self.build()
        self.title_icon = tk.PhotoImage(file=str(ASSETS / 'hergel-studio.png'))
        self.iconphoto(True, self.title_icon)
        if sys.platform == 'win32':
            self.iconbitmap(str(ASSETS / 'hergel.ico'))
        self.after(120, lambda: style_title_bar(self))
        self.show_home()
        self.after(400, self.animate_home)
        self.after(440, self.animate_pack)
        self.after(100, self.poll)
        self.load()
        self.after(500, self.restore_login)
        self.after(1800, self.check_launcher_updates)

    def build(self):
        self.ant_icon = tk.PhotoImage(file=str(ASSETS / 'hormiguerologo.png')).subsample(18)
        self.pack_logo = tk.PhotoImage(file=str(ASSETS / 'logofondo.png')).subsample(3)
        self.pack_logo_small = tk.PhotoImage(file=str(ASSETS / 'logofondo.png')).subsample(4)
        self.home_icon = tk.PhotoImage(file=str(ASSETS / 'iconocasalauncher.png')).subsample(18)
        self.cat_icon = tk.PhotoImage(file=str(ASSETS / 'hergel-studio.png')).subsample(4)
        self.background = tk.PhotoImage(file=str(ASSETS / 'gradient' / '00.png'))
        self.red_background = tk.PhotoImage(file=str(ASSETS / 'red_gradient' / '00.png'))
        sidebar = tk.Frame(self, bg='#171120', width=132)
        sidebar.pack(side='left', fill='y')
        sidebar.pack_propagate(False)
        self.home_button = tk.Button(sidebar, image=self.home_icon, command=self.show_home,
                                     bg='#171120', activebackground=PANEL_LIGHT,
                                     relief='flat', cursor='hand2', borderwidth=0,
                                     highlightthickness=0)
        self.home_button.pack(padx=10, pady=(20, 48))
        self.ant_button = tk.Button(sidebar, image=self.ant_icon, command=self.show_pack,
                                    bg=SIDEBAR, activebackground=PANEL_LIGHT,
                                    relief='flat', cursor='hand2', borderwidth=0,
                                    highlightthickness=0)
        self.ant_button.pack(padx=10, pady=5)
        try:
            placeholder = render_placeholder_bust()
            self.placeholder_image = tk.PhotoImage(data=base64.b64encode(placeholder).decode('ascii'))
        except ImportError:
            # Keep the window usable even before dependencies are installed.
            self.placeholder_image = tk.PhotoImage(width=100, height=100)
            self.placeholder_image.put('#2d2049', to=(0, 0, 100, 100))
            self.placeholder_image.put('#9999aa', to=(30, 45, 70, 95))
            self.placeholder_image.put('#b1b1bc', to=(30, 5, 70, 45))
        self.avatar_frame = tk.Frame(sidebar, bg='#9b6aff', width=108, height=108,
                                     highlightbackground='#c09dff', highlightthickness=1)
        self.avatar_frame.pack_propagate(False)
        self.avatar_button = tk.Button(self.avatar_frame, image=self.placeholder_image,
                                       command=self.account_menu, bg='#2d2049',
                                       activebackground='#3b285d', relief='flat',
                                       borderwidth=0, highlightthickness=0, cursor='hand2')
        self.avatar_button.pack(fill='both', expand=True, padx=3, pady=3)
        self.account_name = label(sidebar, 'Iniciar Sesión', size=10, color=LAVENDER,
                                  weight='bold',
                                  bg='#171120', wraplength=124)
        self.account_name.pack(side='bottom', padx=4, pady=(4, 20))
        self.avatar_frame.pack(side='bottom', padx=6, pady=(0, 0))
        self.settings_button = button(sidebar, 'Ajustes', self.show_settings, padx=10, pady=10)
        self.settings_button.config(bg=SIDEBAR, activebackground=SIDEBAR, fg=MUTED,
                                    highlightthickness=0, activeforeground=LAVENDER)
        self.settings_button.pack(side='bottom', fill='x', padx=10, pady=(0, 12))
        self.settings_button.bind('<Enter>', lambda event: self.settings_button.config(fg=LAVENDER))
        self.settings_button.bind('<Leave>', lambda event: self.settings_button.config(fg=MUTED))

        self.stage = tk.Frame(self, bg=BG)
        self.stage.pack(side='left', fill='both', expand=True)
        self.update_button = button(self.stage, 'Actualizar launcher', self.show_launcher_update, primary=True, padx=12, pady=7)
        self.home_page = tk.Frame(self.stage, bg=BG)
        self.home_canvas = tk.Canvas(self.home_page, bg=BG, highlightthickness=0)
        self.home_canvas.pack(fill='both', expand=True)
        self.home_canvas.bind('<Configure>', self.draw_home)

        self.pack_page = tk.Canvas(self.stage, bg=BG, highlightthickness=0)
        self.pack_page.bind('<Configure>', self.draw_pack)
        self.install_button = button(self.pack_page, '↓  DESCARGAR / ACTUALIZAR',
                                     self.start_install, width=33)
        self.install_button.config(bg='#8c2833', activebackground='#b83742')
        self.play_button = button(self.pack_page, '▶  JUGAR', self.start_play, width=33)
        self.play_button.config(bg='#514061', activebackground='#69517d')

    def show_login_required(self):
        dialog = tk.Toplevel(self)
        dialog.title('El Hormiguero')
        dialog.configure(bg=PANEL)
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        label(dialog, 'INICIA SESIÓN', size=15, color=LAVENDER, weight='bold', bg=PANEL).pack(
            padx=34, pady=(27, 9))
        label(dialog, 'Primero debes iniciar sesión con tu cuenta de Minecraft Java.',
              size=11, bg=PANEL, wraplength=330).pack(padx=30, pady=(0, 22))
        button(dialog, 'ENTENDIDO', dialog.destroy, primary=True).pack(pady=(0, 25))
        dialog.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - dialog.winfo_width()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f'+{x}+{y}')
        dialog.focus_set()

    def start_microsoft_login(self):
        if self.account_busy:
            return
        try:
            client_id = get_client_id()
        except Exception as exc:
            messagebox.showerror('Cuenta Microsoft', str(exc))
            return
        if not client_id:
            messagebox.showinfo('Cuenta Microsoft',
                'El inicio de sesión requiere registrar Hergel Launcher con Microsoft. '
                'El responsable del launcher debe colocar su ID de aplicación en microsoft_app.json. '
                'Todavía no se ha configurado ese ID.')
            return
        self.account_busy = True
        self.avatar_button.config(state='disabled')
        def work():
            try:
                self.events.put(('account', sign_in(client_id)))
            except Exception as exc:
                self.events.put(('account_error', str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def show_home(self):
        self.pack_page.pack_forget()
        self.home_page.pack(fill='both', expand=True)
        self.home_canvas.after_idle(lambda: self.draw_home(None))

    def show_pack(self):
        self.home_page.pack_forget()
        self.pack_page.pack(fill='both', expand=True)
        self.pack_page.after_idle(lambda: self.draw_pack(None))

    def animate_home(self):
        if self.home_page.winfo_ismapped() and self.home_animation_enabled:
            try:
                next_frame = (self.gradient_frame + 1) % 32
                self.background = tk.PhotoImage(file=str(ASSETS / 'gradient' / f'{next_frame:02d}.png'))
                self.gradient_frame = next_frame
                self.draw_home(None)
            except tk.TclError:
                self.home_animation_enabled = False
        self.after(400, self.animate_home)

    def animate_pack(self):
        if self.pack_page.winfo_ismapped() and self.pack_animation_enabled:
            try:
                next_frame = (self.red_frame + 1) % 32
                self.red_background = tk.PhotoImage(file=str(ASSETS / 'red_gradient' / f'{next_frame:02d}.png'))
                self.red_frame = next_frame
                self.draw_pack(None)
            except tk.TclError:
                self.pack_animation_enabled = False
        self.after(440, self.animate_pack)

    def refresh_pack_status(self):
        if self.pack_page.winfo_ismapped():
            self.draw_pack(None)

    def draw_pack(self, event):
        canvas = self.pack_page
        canvas.delete('all')
        w, h = canvas.winfo_width(), canvas.winfo_height()
        if w < 200 or h < 200:
            return
        background = self.red_background
        scale = max(1, -(-w // background.width()), -(-h // background.height()))
        self.active_red_background = background.zoom(scale) if scale > 1 else background
        canvas.create_image(w/2, h/2, image=self.active_red_background)
        canvas.create_text(32, 35, text='EL HORMIGUERO', anchor='w',
                           fill='#f5d2ca', font=(FONT, 13, 'bold'))
        canvas.create_text(w-32, 35, text='MINECRAFT JAVA', anchor='e',
                           fill=MUTED, font=(FONT, 9))
        logo = self.pack_logo if w >= 1050 else self.pack_logo_small
        logo_y = max(165, h*.40)
        canvas.create_image(w/2, logo_y, image=logo)
        canvas.create_text(w/2, logo_y + logo.height()/2 + 30,
                           text='Forge 1.20.1', fill='#e8c2b8', font=(FONT, 12, 'bold'))
        canvas.create_window(w/2, h-145, window=self.install_button)
        canvas.create_window(w/2, h-91, window=self.play_button)
        if self.install_busy and self.progress_total > 0:
            left, top, width = w/2-165, h-59, 330
            fraction = min(1, max(0, self.progress_current / self.progress_total))
            canvas.create_rectangle(left, top, left+width, top+7,
                                    fill='#38242d', outline='#734153')
            canvas.create_rectangle(left, top, left+width*fraction, top+7,
                                    fill='#d26574', outline='')
            progress_text = f'{self.progress_stage}: {self.progress_current}/{self.progress_total} · {fraction:.0%}'
        else:
            progress_text = self.status.get()[:110]
        canvas.create_text(w/2, h-30, text=progress_text, fill='#e8c2b8',
                           font=(FONT, 9), width=max(200, w-45))
        playable = bool(self.ready_game and self.microsoft_account
                        and self.microsoft_account.get('minecraft_token') and not self.install_busy)
        self.play_button.config(state='normal', bg=PURPLE if playable else '#514061',
                                activebackground='#a77dff' if playable else '#69517d')

    def draw_home(self, event):
        canvas = self.home_canvas
        canvas.delete('all')
        w, h = canvas.winfo_width(), canvas.winfo_height()
        if w < 200 or h < 200:
            return
        background = self.background
        scale = max(1, -(-w // background.width()), -(-h // background.height()))
        self.active_background = background.zoom(scale) if scale > 1 else background
        canvas.create_image(w/2, h/2, image=self.active_background)
        x = max(20, (w - 680) / 2)
        y = h / 2 - 140
        canvas.create_image(x+150, y+140, image=self.cat_icon)
        canvas.create_text(x+330, y+96, text='HERGEL', anchor='w',
                           fill=TEXT, font=(FONT, 54, 'bold'))
        canvas.create_text(x+334, y+168, text='STUDIO', anchor='w',
                           fill=LAVENDER, font=(FONT, 46))
        canvas.create_text(w/2, h-42, text='SELECCIONA UNA MODALIDAD EN LA BARRA IZQUIERDA',
                           fill=MUTED, font=(FONT, 10, 'bold'))

    def load(self):
        source = self.source.get()
        root = self.root_path.get()
        def work():
            try:
                packs = load_catalog(source)['packs']
                pack = next((p for p in packs if p['id'] == 'el-hormiguero'), None)
                ready = installed_game(pack, root) if pack else None
                self.events.put(('catalog', (packs, ready)))
            except Exception as exc:
                self.events.put(('catalog_error', str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def selected(self):
        return next((p for p in self.packs if p['id'] == 'el-hormiguero'), None)

    def show_settings(self):
        if getattr(self, 'settings_dialog', None) and self.settings_dialog.winfo_exists():
            self.settings_dialog.lift()
            return
        dialog = tk.Toplevel(self)
        self.settings_dialog = dialog
        dialog.title('Ajustes · Hergel Launcher')
        dialog.configure(bg=BG)
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.iconphoto(False, self.title_icon)
        if sys.platform == 'win32':
            dialog.iconbitmap(str(ASSETS / 'hergel.ico'))
        dialog.after(100, lambda: style_title_bar(dialog) if dialog.winfo_exists() else None)
        outer = tk.Frame(dialog, bg=BG)
        outer.pack(fill='both', expand=True, padx=28, pady=24)
        heading = tk.Frame(outer, bg=BG)
        heading.pack(fill='x', pady=(0, 20))
        label(heading, 'AJUSTES', 23, TEXT, 'bold').pack(anchor='w')
        label(heading, 'Prepara el launcher a tu medida.', 10, MUTED).pack(anchor='w', pady=(5, 0))
        version_row = tk.Frame(outer, bg=BG)
        version_row.pack(fill='x', pady=(0, 14))
        label(version_row, 'Hergel Launcher ' + VERSION, 9, MUTED).pack(side='left')
        button(version_row, 'Buscar actualizaciones', lambda: (dialog.destroy(), self.check_launcher_updates(False)),
               padx=12, pady=6).pack(side='right')

        card = tk.Frame(outer, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill='x', pady=(0, 14))
        row = tk.Frame(card, bg=PANEL)
        row.pack(fill='x', padx=20, pady=(18, 0))
        label(row, 'Memoria de Minecraft', 12, TEXT, 'bold').pack(side='left')
        ram = tk.IntVar(value=self.memory_gb.get())
        badge = label(row, str(ram.get()) + ' GB', 17, LAVENDER, 'bold')
        badge.pack(side='right')
        def update_ram(value):
            badge.config(text=str(int(float(value))) + ' GB')
        slider = tk.Scale(card, from_=2, to=16, resolution=1, variable=ram,
                          command=update_ram, orient='horizontal', showvalue=False,
                          bg=PANEL, fg=TEXT, troughcolor='#100c1b', activebackground=LAVENDER,
                          highlightthickness=0, borderwidth=0, sliderrelief='flat',
                          sliderlength=22, width=8, length=460)
        slider.pack(fill='x', padx=18, pady=(14, 4))
        limits = tk.Frame(card, bg=PANEL)
        limits.pack(fill='x', padx=20)
        label(limits, '2 GB', 9, MUTED).pack(side='left')
        label(limits, '16 GB', 9, MUTED).pack(side='right')
        label(card, '4 GB como punto de partida. Deja memoria libre para Windows.',
              10, MUTED, wraplength=460, justify='left').pack(anchor='w', padx=20, pady=(12, 18))

        feedback = label(outer, '', 10, '#f0a5bd', wraplength=470, justify='left')
        feedback.pack(anchor='w', pady=(10, 0))
        def save():
            try:
                ram_mb(ram.get())
                save_settings(ram_gb=ram.get())
                self.memory_gb.set(ram.get())
                dialog.destroy()
            except Exception as exc:
                feedback.config(text=str(exc))
        actions = tk.Frame(outer, bg=BG)
        actions.pack(fill='x', pady=(10, 0))
        button(actions, 'Guardar cambios', save, primary=True, padx=22).pack(side='right')
        button(actions, 'Cancelar', dialog.destroy, padx=16).pack(side='right', padx=(0, 10))
        dialog.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - dialog.winfo_reqwidth()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - dialog.winfo_reqheight()) // 2
        dialog.geometry(f'+{max(0, x)}+{max(0, y)}')
        dialog.grab_set()
        dialog.focus_set()

    def check_launcher_updates(self, silent=True):
        if self.update_check_busy or self.update_busy:
            return
        self.update_check_busy = True
        def work():
            try:
                release = check_update()
                self.events.put(('launcher_update_check', (release, silent)))
            except Exception as exc:
                self.events.put(('launcher_update_check_error', (str(exc), silent)))
        threading.Thread(target=work, daemon=True).start()

    def show_launcher_update(self):
        if not self.launcher_update:
            return
        if getattr(self, 'update_dialog', None) and self.update_dialog.winfo_exists():
            self.update_dialog.lift()
            return
        release = self.launcher_update
        dialog = tk.Toplevel(self)
        self.update_dialog = dialog
        dialog.title('Actualizar · Hergel Launcher')
        dialog.configure(bg=BG)
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.iconphoto(False, self.title_icon)
        dialog.after(100, lambda: style_title_bar(dialog) if dialog.winfo_exists() else None)
        label(dialog, 'NUEVA VERSIÓN DISPONIBLE', 18, TEXT, 'bold').pack(anchor='w', padx=26, pady=(24, 8))
        label(dialog, VERSION + '  →  ' + release['version'], 13, LAVENDER, 'bold').pack(anchor='w', padx=26)
        if release['required']:
            label(dialog, 'Esta actualización es necesaria para seguir jugando.', 10, MUTED,
                  wraplength=440, justify='left').pack(anchor='w', padx=26, pady=(12, 12))
        notes = release.get('notes', '')[:1500]
        if notes:
            label(dialog, notes, 10, TEXT, wraplength=440, justify='left', bg=PANEL).pack(fill='x', padx=26, pady=(0, 14), ipadx=10, ipady=12)
        self.update_feedback = label(dialog, 'Se conservarán tu cuenta, tus ajustes y el modpack.', 10, MUTED, wraplength=440, justify='left')
        self.update_feedback.pack(anchor='w', padx=26, pady=(0, 8))
        actions = tk.Frame(dialog, bg=BG)
        actions.pack(fill='x', padx=26, pady=(10, 24))
        self.update_confirm = button(actions, 'Actualizar ahora', self.begin_launcher_update, primary=True)
        self.update_confirm.pack(side='right')
        self.update_later = button(actions, 'Cerrar' if release['required'] else 'Más tarde', dialog.destroy)
        self.update_later.pack(side='right', padx=(0, 10))
        dialog.protocol('WM_DELETE_WINDOW', lambda: None if self.update_busy else dialog.destroy())
        dialog.update_idletasks()
        dialog.geometry(f'+{max(0, self.winfo_rootx() + (self.winfo_width() - dialog.winfo_reqwidth()) // 2)}+{max(0, self.winfo_rooty() + (self.winfo_height() - dialog.winfo_reqheight()) // 2)}')
        dialog.grab_set()

    def begin_launcher_update(self):
        if self.update_busy:
            return
        if self.install_busy or self.account_busy:
            self.update_feedback.config(text='Espera a que termine la operación actual y vuelve a pulsar Actualizar.')
            return
        if sys.platform != 'win32':
            self.update_feedback.config(text='Esta actualización del instalador está disponible en Windows.')
            return
        self.update_busy = True
        self.update_confirm.config(state='disabled')
        self.update_later.config(state='disabled')
        self.update_feedback.config(text='Descargando y verificando la actualización...')
        release = self.launcher_update.copy()
        def work():
            try:
                installer = download_update(release, lambda current, total:
                    self.events.put(('launcher_update_progress', (current, total))))
                self.events.put(('launcher_update_ready', (installer, release)))
            except Exception as exc:
                self.events.put(('launcher_update_error', str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def account_menu(self):
        if self.account_busy:
            return
        if not self.microsoft_account:
            self.start_microsoft_login()
            return
        menu = tk.Menu(self, tearoff=False, bg=PANEL, fg=TEXT)
        menu.add_command(label='Cambiar cuenta', command=self.start_microsoft_login)
        menu.add_command(label='Cerrar sesión', command=self.logout)
        menu.tk_popup(self.avatar_button.winfo_rootx() + 100, self.avatar_button.winfo_rooty())

    def logout(self):
        if self.account_busy:
            return
        try:
            sign_out(get_client_id())
            self.microsoft_account = None
            self.avatar_button.config(image=self.placeholder_image)
            self.account_name.config(text='Iniciar Sesión')
            self.status.set('Sesión cerrada')
            self.refresh_pack_status()
        except Exception as exc:
            messagebox.showerror('Cerrar sesión', str(exc))

    def restore_login(self):
        if self.account_busy or self.microsoft_account:
            return
        self.account_busy = True
        self.avatar_button.config(state='disabled')
        def work():
            try:
                self.events.put(('account_silent', restore_session(get_client_id())))
            except Exception:
                self.events.put(('account_silent', None))
        threading.Thread(target=work, daemon=True).start()

    def open_instance(self):
        pack = self.selected()
        if pack:
            folder = Path(self.root_path.get()).expanduser() / pack['id']
            folder.mkdir(parents=True, exist_ok=True)
            open_folder(folder)

    def start_install(self):
        pack = self.selected()
        if not pack:
            messagebox.showinfo('Hergel Launcher', 'Selecciona una modalidad.')
            return
        if self.install_busy or self.update_busy:
            return
        self.install_busy = True
        self.ready_game = None
        self.progress_stage = ''
        self.progress_current = 0
        self.progress_total = 0
        self.status.set('Preparando descarga de Minecraft y Forge...')
        self.install_button.config(state='disabled')
        root = self.root_path.get()
        source = self.source.get()
        def work():
            try:
                fresh = load_catalog(source)['packs']
                latest = next(p for p in fresh if p['id'] == pack['id'])
                self.events.put(('catalog_packs', fresh))
                folder, version = prepare_game(
                    latest, root, lambda msg: self.events.put(('status', msg)),
                    lambda stage, current, total: self.events.put(('progress', (stage, current, total))))
                self.events.put(('done', (folder, version)))
            except Exception as exc:
                self.events.put(('error', str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def start_play(self):
        if self.update_required:
            self.show_launcher_update()
            return
        if self.update_busy:
            return
        if not self.microsoft_account or not self.microsoft_account.get('minecraft_token'):
            self.show_login_required()
            return
        if self.install_busy or self.account_busy:
            return
        if not self.ready_game:
            messagebox.showinfo('El Hormiguero', 'Descarga la modalidad antes de jugar.')
            return
        folder, version = self.ready_game
        memory = self.memory_gb.get()
        self.account_busy = True
        self.avatar_button.config(state='disabled')
        self.status.set('Renovando sesión de Minecraft...')
        server = self.selected().get('server') if self.selected() else None
        self.play_button.config(bg='#514061')
        def work():
            try:
                account = restore_session(get_client_id())
                if not account:
                    self.events.put(('session_expired', None))
                    return
                self.events.put(('account_renewed', account))
                process = launch_game(folder, version, account, server, memory_gb=memory)
                self.events.put(('launched', process.pid))
            except Exception as exc:
                self.events.put(('launch_error', str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        try:
            while True:
                kind, message = self.events.get_nowait()
                if kind == 'launcher_update_check':
                    self.update_check_busy = False
                    release, silent = message
                    if release:
                        self.launcher_update = release
                        self.update_required = release['required']
                        self.update_button.config(text='Actualizar a ' + release['version'])
                        self.update_button.place(relx=1, x=-20, y=16, anchor='ne')
                        self.update_button.lift()
                        self.show_launcher_update()
                    elif not silent:
                        messagebox.showinfo('Actualizaciones', 'No hay una versión nueva disponible. Si el alojamiento aún no está configurado, se usará esta versión.')
                    continue
                if kind == 'launcher_update_check_error':
                    self.update_check_busy = False
                    error, silent = message
                    if not silent:
                        messagebox.showerror('Actualizaciones', 'No se pudo comprobar la versión. ' + error)
                    continue
                if kind == 'launcher_update_progress':
                    current, total = message
                    self.update_feedback.config(text=f'Descargando actualización · {int(100 * current / total)} %')
                    continue
                if kind == 'launcher_update_ready':
                    installer, release = message
                    try:
                        launch_installer(installer, release)
                        self.destroy()
                        return
                    except Exception as exc:
                        self.events.put(('launcher_update_error', str(exc)))
                    continue
                if kind == 'launcher_update_error':
                    self.update_busy = False
                    self.update_confirm.config(state='normal')
                    self.update_later.config(state='normal')
                    self.update_feedback.config(text='No se pudo actualizar. ' + message)
                    continue
                if kind == 'catalog_packs':
                    self.packs = message
                    continue
                if kind == 'catalog':
                    self.packs, ready = message
                    if not self.install_busy:
                        self.ready_game = ready
                        self.status.set('Instalación completa' if self.ready_game else 'Pulsa Descargar para instalar o actualizar El Hormiguero')
                    self.refresh_pack_status()
                    continue
                if kind == 'catalog_error':
                    self.status.set('No se pudieron consultar las actualizaciones. Revisa la conexión a Internet.')
                    continue
                if kind == 'session_expired':
                    self.account_busy = False
                    self.microsoft_account = None
                    self.avatar_button.config(state='normal', image=self.placeholder_image)
                    self.account_name.config(text='Iniciar Sesión')
                    self.show_login_required()
                    self.refresh_pack_status()
                    continue
                if kind == 'account_silent' and message is None:
                    self.account_busy = False
                    self.avatar_button.config(state='normal')
                    continue
                if kind in ('account', 'account_silent', 'account_renewed'):
                    if kind != 'account_renewed':
                        self.account_busy = False
                        self.avatar_button.config(state='normal')
                    self.microsoft_account = message
                    name = message['display_name']
                    self.account_name.config(text=message.get('minecraft_name') or 'Iniciar Sesión')
                    bust = message.get('skin_bust')
                    if bust and message.get('minecraft_name'):
                        self.skin_image = tk.PhotoImage(data=base64.b64encode(bust).decode('ascii'))
                        self.avatar_button.config(image=self.skin_image)
                    else:
                        self.avatar_button.config(image=self.placeholder_image)
                    if kind in ('account_silent', 'account_renewed'):
                        self.refresh_pack_status()
                        continue
                    if message.get('minecraft_error'):
                        messagebox.showwarning('Perfil de Minecraft',
                            f'Sesión Microsoft iniciada como {name}. No se puede jugar con esta sesión: '
                            f"{message['minecraft_error']}")
                    elif message.get('skin_error'):
                        messagebox.showwarning('Skin de Minecraft',
                            f"Cuenta Minecraft: {message['minecraft_name']}. No se pudo cargar su skin: "
                            f"{message['skin_error']}")
                    else:
                        messagebox.showinfo('Perfil de Minecraft',
                            f"Cuenta Minecraft: {message['minecraft_name']}")
                    self.refresh_pack_status()
                    continue
                if kind == 'account_error':
                    self.account_busy = False
                    self.avatar_button.config(state='normal')
                    messagebox.showerror('Cuenta Microsoft', message)
                    continue
                if kind == 'status':
                    self.status.set(message)
                    continue
                if kind == 'progress':
                    self.progress_stage, self.progress_current, self.progress_total = message
                    continue
                if kind == 'done':
                    self.ready_game = message
                    self.install_busy = False
                    self.progress_total = 0
                    self.install_button.config(state='normal')
                    self.status.set('Instalación completa')
                    self.refresh_pack_status()
                    continue
                if kind == 'launched':
                    self.account_busy = False
                    self.avatar_button.config(state='normal')
                    self.status.set('Minecraft iniciado.')
                    self.refresh_pack_status()
                    continue
                if kind == 'launch_error':
                    self.account_busy = False
                    self.avatar_button.config(state='normal')
                    self.refresh_pack_status()
                    messagebox.showerror('No se pudo iniciar Minecraft', message)
                    continue
                self.status.set(message)
                if kind == 'error':
                    self.install_busy = False
                    self.progress_total = 0
                    self.install_button.config(state='normal')
                    self.refresh_pack_status()
                    messagebox.showerror('Error de instalación', message)
        except queue.Empty:
            pass
        self.after(100, self.poll)


def main():
    App().mainloop()
