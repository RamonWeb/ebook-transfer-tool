import os
import smtplib
import json
import shutil
import sys
from tkinter import *
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, Optional, List

CONFIG_FILE = "config.json"


def load_config() -> Dict:
    """Lädt die Konfigurationsdatei oder gibt Standardwerte zurück."""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as file:
                return json.load(file)
    except json.JSONDecodeError:
        messagebox.showerror("Fehler", "Die Konfigurationsdatei ist beschädigt.")
    return {
        "source_folder": "",
        "sent_folder": "",
        "smtp_server": "",
        "smtp_port": 587,
        "username": "",
        "password": "",
        "kindle1": "",
        "kindle2": "",
        "active_kindle": "kindle1",
        "tolino_enabled": False
    }


def save_config(config_data: Dict) -> None:
    """Speichert die Konfigurationsdatei."""
    with open(CONFIG_FILE, "w") as file:
        json.dump(config_data, file, indent=4)


def select_folder(entry: Entry) -> None:
    """Öffnet einen Dialog zur Auswahl eines Ordners."""
    folder = filedialog.askdirectory()
    if folder:
        entry.delete(0, END)
        entry.insert(0, folder)


def detect_tolino() -> Optional[str]:
    """Erkennt angeschlossene Tolino-Geräte und gibt den Pfad zum Download-Ordner zurück."""
    possible_mount_points = []
    
    if sys.platform == 'win32':
        # Windows: Laufwerke von D: bis Z:
        for drive in 'DEFGHIJKLMNOPQRSTUVWXYZ':
            path = f"{drive}:\\"
            if os.path.exists(path):
                possible_mount_points.append(path)
    elif sys.platform == 'darwin':
        # macOS: Typische Mount-Points
        possible_mount_points.extend([
            '/Volumes/TOLINO',
            '/Volumes/Tolino'
        ])
    else:
        # Linux und andere Unix-Systeme
        possible_mount_points.extend([
            '/media/' + os.getenv('USER') + '/tolino',
            '/media/TOLINO',
            '/media/Tolino',
            '/run/media/' + os.getenv('USER') + '/TOLINO',
            '/mnt/TOLINO'
        ])
    
    for mount_point in possible_mount_points:
        if os.path.exists(mount_point):
            # Suche nach dem Download-Ordner
            for folder_name in ['downloads', 'Downloads']:
                download_path = os.path.join(mount_point, folder_name)
                if os.path.isdir(download_path):
                    return download_path
    return None


def copy_to_tolino(epub_files: List[str]) -> bool:
    """Kopiert EPUB-Dateien auf den Tolino."""
    tolino_download = detect_tolino()
    
    if not tolino_download:
        messagebox.showerror("Fehler", "Kein Tolino-Gerät gefunden. Bitte verbinden Sie den Tolino per USB.")
        return False
    
    success = True
    for epub_file in epub_files:
        if not os.path.isfile(epub_file):
            messagebox.showwarning("Warnung", f"Datei {epub_file} existiert nicht und wird übersprungen.")
            continue
        
        filename = os.path.basename(epub_file)
        dest_path = os.path.join(tolino_download, filename)
        
        try:
            shutil.copy2(epub_file, dest_path)
            messagebox.showinfo("Erfolg", f"Datei kopiert: {filename} -> Tolino")
        except Exception as e:
            messagebox.showerror("Fehler", f"Problem beim Kopieren von {filename}: {str(e)}")
            success = False
    
    return success


def send_email(epub_file: str, recipient_email: str, config: Dict) -> bool:
    """Sendet eine E-Mail mit der EPUB-Datei."""
    try:
        msg = MIMEMultipart()
        msg["From"] = config["username"]
        msg["To"] = recipient_email
        msg["Subject"] = "Your Kindle Document"

        with open(epub_file, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(epub_file)}")
        msg.attach(part)

        with smtplib.SMTP(config["smtp_server"], config["smtp_port"]) as server:
            server.starttls()
            server.login(config["username"], config["password"])
            server.send_message(msg)
        return True
    except Exception as e:
        messagebox.showerror("Fehler", f"Fehler beim Senden: {e}")
        return False


def process_files(config: Dict) -> None:
    """Verarbeitet die Dateien im Quellordner und sendet sie per E-Mail oder kopiert sie auf Tolino."""
    source_folder = config["source_folder"]
    sent_folder = config["sent_folder"]

    if not os.path.exists(source_folder):
        messagebox.showerror("Fehler", "Quellordner existiert nicht!")
        return

    files = [os.path.join(source_folder, f) for f in os.listdir(source_folder) if f.endswith(".epub")]
    if not files:
        messagebox.showinfo("Info", "Keine EPUB-Dateien gefunden.")
        return

    if config.get("tolino_enabled", False):
        # Tolino-Modus
        if copy_to_tolino(files):
            # Dateien verschieben nach erfolgreicher Übertragung
            for file in files:
                try:
                    if not os.path.exists(sent_folder):
                        os.makedirs(sent_folder)
                    
                    new_path = os.path.join(sent_folder, os.path.basename(file))
                    if os.path.exists(new_path):
                        base, ext = os.path.splitext(os.path.basename(file))
                        counter = 1
                        while os.path.exists(new_path):
                            new_path = os.path.join(sent_folder, f"{base}_{counter}{ext}")
                            counter += 1
                    
                    os.rename(file, new_path)
                except Exception as e:
                    messagebox.showerror("Fehler", f"Problem beim Verschieben von {file}: {e}")
    else:
        # E-Mail-Modus (Kindle)
        recipient_email = config[config["active_kindle"]]
        if not recipient_email:
            messagebox.showerror("Fehler", "Keine Kindle-E-Mail-Adresse konfiguriert!")
            return

        for file in files:
            try:
                if send_email(file, recipient_email, config):
                    messagebox.showinfo("Erfolg", f"Datei gesendet: {os.path.basename(file)}")

                    if not os.path.exists(sent_folder):
                        os.makedirs(sent_folder)

                    new_path = os.path.join(sent_folder, os.path.basename(file))
                    if os.path.exists(new_path):
                        base, ext = os.path.splitext(os.path.basename(file))
                        counter = 1
                        while os.path.exists(new_path):
                            new_path = os.path.join(sent_folder, f"{base}_{counter}{ext}")
                            counter += 1

                    os.rename(file, new_path)
            except Exception as e:
                messagebox.showerror("Fehler", f"Problem mit Datei {os.path.basename(file)}: {e}")


def preview_files(config: Dict) -> None:
    """Zeigt eine Vorschau der Dateien im Quellordner."""
    source_folder = config["source_folder"]

    if not os.path.exists(source_folder):
        messagebox.showerror("Fehler", "Quellordner existiert nicht!")
        return

    files = [f for f in os.listdir(source_folder) if f.endswith(".epub")]
    if not files:
        messagebox.showinfo("Info", "Keine EPUB-Dateien gefunden.")
    else:
        preview_window = Toplevel()
        preview_window.title("Vorschau der Dateien")

        Label(preview_window, text="Folgende Dateien sind bereit:", font=("Arial", 12, "bold")).pack(pady=10)

        listbox = Listbox(preview_window, width=50, height=15)
        listbox.pack(pady=10, padx=10)

        for file in files:
            listbox.insert(END, file)

        Button(preview_window, text="Schließen", command=preview_window.destroy).pack(pady=10)


def open_config_window(config: Dict, update_callback: callable) -> None:
    """Öffnet das Konfigurationsfenster."""
    config_window = Toplevel()
    config_window.title("Konfiguration")

    # GUI-Elemente für die Konfiguration
    row = 0
    
    Label(config_window, text="Quellordner:").grid(row=row, column=0, padx=5, pady=5)
    source_folder_entry = Entry(config_window, width=40)
    source_folder_entry.grid(row=row, column=1, padx=5, pady=5)
    source_folder_entry.insert(0, config.get("source_folder", ""))
    Button(config_window, text="Durchsuchen", command=lambda: select_folder(source_folder_entry)).grid(row=row, column=2, padx=5, pady=5)
    row += 1

    Label(config_window, text="Gesendet-Ordner:").grid(row=row, column=0, padx=5, pady=5)
    sent_folder_entry = Entry(config_window, width=40)
    sent_folder_entry.grid(row=row, column=1, padx=5, pady=5)
    sent_folder_entry.insert(0, config.get("sent_folder", ""))
    Button(config_window, text="Durchsuchen", command=lambda: select_folder(sent_folder_entry)).grid(row=row, column=2, padx=5, pady=5)
    row += 1

    # Tolino-Einstellungen
    tolino_var = BooleanVar(value=config.get("tolino_enabled", False))
    Checkbutton(config_window, text="Tolino-Modus aktivieren", variable=tolino_var).grid(row=row, column=0, columnspan=3, pady=10, sticky="w")
    row += 1

    # Nur zeigen, wenn Tolino-Modus nicht aktiv ist
    def toggle_kindle_fields():
        state = NORMAL if not tolino_var.get() else DISABLED
        smtp_entry.config(state=state)
        port_entry.config(state=state)
        email_entry.config(state=state)
        password_entry.config(state=state)
        kindle1_entry.config(state=state)
        kindle2_entry.config(state=state)
        active_kindle_var.set("kindle1" if state == NORMAL else "")
        rb_kindle1.config(state=state)
        rb_kindle2.config(state=state)

    tolino_var.trace("w", lambda *args: toggle_kindle_fields())

    Label(config_window, text="SMTP-Server:").grid(row=row, column=0, padx=5, pady=5)
    smtp_entry = Entry(config_window, width=40)
    smtp_entry.grid(row=row, column=1, padx=5, pady=5)
    smtp_entry.insert(0, config.get("smtp_server", ""))
    row += 1

    Label(config_window, text="SMTP-Port:").grid(row=row, column=0, padx=5, pady=5)
    port_entry = Entry(config_window, width=40)
    port_entry.grid(row=row, column=1, padx=5, pady=5)
    port_entry.insert(0, config.get("smtp_port", ""))
    row += 1

    Label(config_window, text="Absender E-Mail:").grid(row=row, column=0, padx=5, pady=5)
    email_entry = Entry(config_window, width=40)
    email_entry.grid(row=row, column=1, padx=5, pady=5)
    email_entry.insert(0, config.get("username", ""))
    row += 1

    Label(config_window, text="Passwort:").grid(row=row, column=0, padx=5, pady=5)
    password_entry = Entry(config_window, show="*", width=40)
    password_entry.grid(row=row, column=1, padx=5, pady=5)
    password_entry.insert(0, config.get("password", ""))
    row += 1

    Label(config_window, text="Kindle1 E-Mail:").grid(row=row, column=0, padx=5, pady=5)
    kindle1_entry = Entry(config_window, width=40)
    kindle1_entry.grid(row=row, column=1, padx=5, pady=5)
    kindle1_entry.insert(0, config.get("kindle1", ""))
    row += 1

    Label(config_window, text="Kindle2 E-Mail:").grid(row=row, column=0, padx=5, pady=5)
    kindle2_entry = Entry(config_window, width=40)
    kindle2_entry.grid(row=row, column=1, padx=5, pady=5)
    kindle2_entry.insert(0, config.get("kindle2", ""))
    row += 1

    Label(config_window, text="Aktive Kindle-Adresse:").grid(row=row, column=0, padx=5, pady=5)
    active_kindle_var = StringVar(value=config.get("active_kindle", "kindle1"))
    rb_kindle1 = Radiobutton(config_window, text="Kindle1", variable=active_kindle_var, value="kindle1")
    rb_kindle1.grid(row=row, column=1, sticky="w")
    rb_kindle2 = Radiobutton(config_window, text="Kindle2", variable=active_kindle_var, value="kindle2")
    rb_kindle2.grid(row=row+1, column=1, sticky="w")
    row += 2

    def save_and_close() -> None:
        """Speichert die Konfiguration und schließt das Fenster."""
        new_config = {
            "source_folder": source_folder_entry.get(),
            "sent_folder": sent_folder_entry.get(),
            "smtp_server": smtp_entry.get(),
            "smtp_port": int(port_entry.get()) if port_entry.get() else 587,
            "username": email_entry.get(),
            "password": password_entry.get(),
            "kindle1": kindle1_entry.get(),
            "kindle2": kindle2_entry.get(),
            "active_kindle": active_kindle_var.get(),
            "tolino_enabled": tolino_var.get()
        }
        save_config(new_config)
        config.update(new_config)
        update_callback()  # Hier rufen wir die Callback-Funktion auf
        config_window.destroy()

    Button(config_window, text="Speichern", command=save_and_close).grid(row=row, column=0, columnspan=3, pady=10)
    
    # Initialen Zustand setzen
    toggle_kindle_fields()


def main() -> None:
    """Startet die Haupt-GUI."""
    config = load_config()

    root = Tk()
    root.title("eBook Transfer Tool - Kindle & Tolino")
    root.geometry("800x600")

    # Hintergrundbild setzen
    try:
        bg_image = Image.open("background.jpg")
        bg_photo = ImageTk.PhotoImage(bg_image.resize((800, 600)))
        background_label = Label(root, image=bg_photo)
        background_label.place(x=0, y=0, relwidth=1, relheight=1)
    except FileNotFoundError:
        print("Hintergrundbild nicht gefunden. Verwende Standardhintergrund.")

    # Icons laden
    try:
        config_icon = PhotoImage(file="configure.png")
        preview_icon = PhotoImage(file="preview.png")
        start_icon = PhotoImage(file="start.png")
    except FileNotFoundError:
        print("Icons nicht gefunden. Verwende Textbuttons.")

    # Statusanzeige für den aktuellen Modus
    mode_var = StringVar()
    mode_var.set(f"Aktueller Modus: {'Tolino' if config.get('tolino_enabled', False) else 'Kindle (E-Mail)'}")
    mode_label = Label(root, textvariable=mode_var, font=("Arial", 12, "bold"), bg="white")
    mode_label.pack(side=TOP, pady=20)

    def update_mode_display():
        """Aktualisiert die Modusanzeige basierend auf der aktuellen Konfiguration."""
        mode_var.set(f"Aktueller Modus: {'Tolino' if config.get('tolino_enabled', False) else 'Kindle (E-Mail)'}")

    def open_config_window_wrapper():
        """Wrapper-Funktion für das Konfigurationsfenster mit Callback."""
        open_config_window(config, update_mode_display)

    # Buttons nebeneinander am unteren Rand positionieren
    button_frame = Frame(root, bg="white")
    button_frame.pack(side="bottom", pady=20)

    Button(button_frame, text="Konfiguration", image=config_icon, compound=TOP, 
           command=open_config_window_wrapper).pack(side=LEFT, padx=20)
    Button(button_frame, text="Vorschau", image=preview_icon, compound=TOP, 
           command=lambda: preview_files(config)).pack(side=LEFT, padx=20)
    Button(button_frame, text="Senden", image=start_icon, compound=TOP, 
           command=lambda: process_files(config)).pack(side=LEFT, padx=20)

    root.mainloop()


if __name__ == "__main__":
    main()
