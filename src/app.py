import asyncio
import datetime
import json
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import queue
import time
from typing import Dict, List, Optional

from tracker import ClassTracker


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Проследяване на уеб елементи")
        self.geometry("1100x800")
        self.tracker = ClassTracker()
        self.data_store: Dict[str, Dict[str, Optional[Dict[str, List[str]]]]] = {}
        self.running = False
        self.manual_running = False
        self.thread = None
        self.q: "queue.Queue[object]" = queue.Queue()
        self.status_var = tk.StringVar(value="Готово")
        self.count_var = tk.StringVar(value="0 URL / 0 селектори")
        self.last_run_var = tk.StringVar(value="Последно извличане: -")
        self.error_var = tk.StringVar(value="")
        self._status_animating = False
        self._status_base = ""
        self._status_phase = 0
        self._status_pulse_colors = ("#0b5a50", "#0f766e")
        self._error_after_id = None
        self._placeholder_style = "Placeholder.TEntry"
        self._url_placeholder = "https://www.olx.bg/avtomobili-karavani-lodki/"
        self._selector_placeholder = ".css-1au435n"
        self.validation_var = tk.StringVar(value="")
        self.url_status: Dict[str, str] = {}

        self.create_widgets()
        self.update_tracked_tree()
        self.update_data_display()
        self.check_queue()

    def create_widgets(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        for font_name in ("TkDefaultFont", "TkTextFont", "TkHeadingFont", "TkMenuFont"):
            try:
                tk_font = tkfont.nametofont(font_name)
                tk_font.configure(size=tk_font.cget("size") + 1)
            except tk.TclError:
                pass

        style.configure("Header.TLabel", font=("TkDefaultFont", 17, "bold"), foreground="#f8fafc")
        style.configure("SubHeader.TLabel", font=("TkDefaultFont", 10))
        style.configure("Hint.TLabel", foreground="#0b5a50")
        style.configure("InlineError.TLabel", foreground="#b91c1c")
        style.configure("Accent.TButton", foreground="#0b2d2b", padding=(14, 8), relief="solid", borderwidth=1)
        style.map(
            "Accent.TButton",
            background=[("active", "#e2e8f0"), ("pressed", "#cbd5e1"), ("!active", "#f1f5f9")],
            foreground=[("active", "#0b2d2b"), ("pressed", "#0b2d2b")],
        )
        style.configure("Accent.Secondary.TButton", foreground="#0f172a", padding=(12, 7), relief="solid", borderwidth=1)
        style.map(
            "Accent.Secondary.TButton",
            background=[("active", "#e2e8f0"), ("pressed", "#cbd5e1"), ("!active", "#f1f5f9")],
            foreground=[("active", "#0f172a"), ("pressed", "#0f172a")],
        )
        style.configure("TProgressbar", troughcolor="#e0f2f1", background="#0b5a50")
        style.configure("TNotebook", background="#0f172a", borderwidth=0)
        style.configure("TNotebook.Tab", background="#0f172a", foreground="#cbd5f5", padding=(10, 6))
        style.map("TNotebook.Tab", background=[("selected", "#0b5a50")], foreground=[("selected", "#f8fafc")])
        style.map("Treeview", background=[("selected", "#0b5a50")], foreground=[("selected", "#f8fafc")])
        style.configure("Treeview", fieldbackground="#f8fafc")
        style.configure("TLabelframe", padding=(12, 10), borderwidth=1, relief="solid")
        style.configure(self._placeholder_style, foreground="#94a3b8")

        header = tk.Frame(self, bg="#0f172a")
        header.pack(fill="x", padx=10, pady=(10, 4))
        ttk.Label(header, text="Проследяване на уеб елементи", style="Header.TLabel", background="#0f172a").pack(side="left", padx=8, pady=6)
        ttk.Label(header, textvariable=self.count_var, style="SubHeader.TLabel").pack(side="right", padx=(8, 16))

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        tab_tracked = ttk.Frame(notebook)
        tab_data = ttk.Frame(notebook)
        tab_log = ttk.Frame(notebook)

        notebook.add(tab_tracked, text="Проследявани")
        notebook.add(tab_data, text="Данни")
        notebook.add(tab_log, text="Лог")

        add_frame = ttk.LabelFrame(tab_tracked, text="Добавяне на URL и селектор")
        add_frame.pack(fill="x", padx=8, pady=8)
        add_frame.grid_columnconfigure(1, weight=1)

        ttk.Label(add_frame, text="URL:").grid(row=0, column=0, sticky="e", padx=(18, 8), pady=5)
        self.entry_url = ttk.Entry(add_frame, width=80)
        self.entry_url.grid(row=0, column=1, padx=5, pady=5, sticky="we")
        self.apply_placeholder(self.entry_url, self._url_placeholder)
        self.entry_url.bind("<FocusIn>", lambda _e: (self.clear_validation(), self.clear_placeholder(self.entry_url, self._url_placeholder)))
        self.entry_url.bind("<FocusOut>", lambda _e: self.restore_placeholder(self.entry_url, self._url_placeholder))

        ttk.Label(add_frame, text="CSS селектор:").grid(row=1, column=0, sticky="e", padx=(18, 8), pady=5)
        self.entry_selector = ttk.Entry(add_frame, width=60)
        self.entry_selector.grid(row=1, column=1, padx=5, pady=5, sticky="we")
        self.apply_placeholder(self.entry_selector, self._selector_placeholder)
        self.entry_selector.bind("<FocusIn>", lambda _e: (self.clear_validation(), self.clear_placeholder(self.entry_selector, self._selector_placeholder)))
        self.entry_selector.bind("<FocusOut>", lambda _e: self.restore_placeholder(self.entry_selector, self._selector_placeholder))

        self.validation_label = ttk.Label(add_frame, textvariable=self.validation_var, style="InlineError.TLabel")
        self.validation_label.grid(row=2, column=1, sticky="w", padx=5, pady=(0, 2))

        info_box = tk.Frame(add_frame, bg="#e0f2f1", highlightbackground="#0b5a50", highlightthickness=1)
        info_box.grid(row=3, column=1, sticky="we", padx=5, pady=(2, 8))
        info_box.grid_columnconfigure(0, weight=1)
        badge = tk.Label(info_box, text="i", bg="#0b5a50", fg="#f8fafc", width=2)
        badge.grid(row=0, column=0, sticky="nw", padx=(8, 0), pady=6)
        badge.bind("<Enter>", lambda _e: badge.config(bg="#0f766e"))
        badge.bind("<Leave>", lambda _e: badge.config(bg="#0b5a50"))
        hint_text = (
            "Очаквано съдържание: пълен URL с http/https. "
            "CSS селекторът е стандартен (например .title, #price, div.item a)."
        )
        hint = tk.Label(info_box, text=hint_text, bg="#e0f2f1", fg="#0b5a50", wraplength=720, justify="left")
        hint.grid(row=0, column=1, sticky="w", padx=(8, 10), pady=6)
        info_box.bind("<Configure>", lambda e: hint.config(wraplength=max(e.width - 80, 240)))

        ttk.Button(add_frame, text="Добави", command=self.add_tracked, style="Accent.TButton").grid(row=4, column=1, pady=6, sticky="e")

        tree_frame = tk.Frame(tab_tracked, highlightbackground="#cbd5e1", highlightthickness=1)
        tree_frame.pack(fill="both", expand=True, padx=8, pady=4)

        self.tree = ttk.Treeview(tree_frame, show="tree headings", columns=("status",))
        self.tree.heading("#0", text="URL / Селектор")
        self.tree.heading("status", text="Статус")
        self.tree.column("#0", width=700, anchor="w")
        self.tree.column("status", width=140, anchor="center")
        self.tree.tag_configure("status-ok", foreground="#0f766e")
        self.tree.tag_configure("status-error", foreground="#b91c1c")
        self.tree.tag_configure("status-warn", foreground="#b45309")
        self.tree.tag_configure("status-neutral", foreground="#64748b")
        self.tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        control_frame = ttk.Frame(tab_tracked)
        control_frame.pack(fill="x", padx=8, pady=8)

        ttk.Button(control_frame, text="Премахни избран елемент", command=self.remove_selected, style="Accent.Secondary.TButton").pack(side="left", padx=5)

        periodic_frame = ttk.LabelFrame(tab_tracked, text="Периодично извличане")
        periodic_frame.pack(fill="x", padx=8, pady=8)

        ttk.Label(periodic_frame, text="Интервал (секунди):").pack(side="left", padx=(18, 8))
        self.entry_interval = ttk.Entry(periodic_frame, width=10)
        self.entry_interval.insert(0, "300")
        self.entry_interval.pack(side="left", padx=5)

        self.btn_start = ttk.Button(periodic_frame, text="Стартирай", command=self.start_periodic, style="Accent.TButton")
        self.btn_start.pack(side="left", padx=10)

        self.btn_stop = ttk.Button(periodic_frame, text="Спри", command=self.stop_periodic, state="disabled", style="Accent.Secondary.TButton")
        self.btn_stop.pack(side="left", padx=5)

        ttk.Button(periodic_frame, text="Извлечи веднъж", command=self.manual_extract, style="Accent.TButton").pack(side="left", padx=20)

        output_font = tkfont.nametofont("TkFixedFont").copy()
        output_font.configure(size=output_font.cget("size") + 1)
        self.data_text = scrolledtext.ScrolledText(tab_data, wrap="word", font=output_font)
        self.data_text.pack(fill="both", expand=True, padx=8, pady=8)

        save_frame = ttk.Frame(tab_data)
        save_frame.pack(pady=10)

        ttk.Button(save_frame, text="Запиши в JSON", command=self.save_json, style="Accent.TButton").pack(side="left", padx=10)
        ttk.Button(save_frame, text="Запиши в CSV", command=self.save_csv, style="Accent.TButton").pack(side="left", padx=10)
        ttk.Button(save_frame, text="Зареди от JSON", command=self.load_json, style="Accent.Secondary.TButton").pack(side="left", padx=10)

        self.log_text = scrolledtext.ScrolledText(tab_log, font=output_font)
        self.log_text.pack(fill="both", expand=True, padx=8, pady=8)

        status = ttk.Frame(self)
        status.pack(fill="x", padx=10, pady=(0, 10))
        self.status_label = ttk.Label(status, textvariable=self.status_var, style="Hint.TLabel")
        self.status_label.pack(side="left")
        ttk.Label(status, textvariable=self.last_run_var).pack(side="left", padx=15)
        self.status_progress = ttk.Progressbar(status, mode="indeterminate", length=140)
        self.status_progress.pack(side="right")
        self.error_frame = tk.Frame(self, bg="#fee2e2", highlightbackground="#b91c1c", highlightthickness=1)
        self.error_label = tk.Label(self.error_frame, textvariable=self.error_var, bg="#fee2e2", fg="#7f1d1d")
        self.error_label.pack(side="left", padx=8, pady=4)

    def log(self, message: str) -> None:
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)

    def clear_validation(self) -> None:
        if self.validation_var.get():
            self.validation_var.set("")

    def apply_placeholder(self, entry: tk.Entry, text: str) -> None:
        entry.delete(0, tk.END)
        entry.insert(0, text)
        entry.configure(style=self._placeholder_style)

    def clear_placeholder(self, entry: tk.Entry, text: str) -> None:
        if entry.get() == text and entry.cget("style") == self._placeholder_style:
            entry.delete(0, tk.END)
            entry.configure(style="TEntry")

    def restore_placeholder(self, entry: tk.Entry, text: str) -> None:
        if not entry.get().strip():
            self.apply_placeholder(entry, text)

    def get_entry_value(self, entry: tk.Entry, placeholder_text: str) -> str:
        value = entry.get().strip()
        if value == placeholder_text and entry.cget("style") == self._placeholder_style:
            return ""
        return value

    def update_tracked_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        selector_count = 0
        for url, selectors in self.tracker.tracked.items():
            status = self.url_status.get(url, "—")
            if status == "OK":
                tag = "status-ok"
            elif status == "Грешка":
                tag = "status-error"
            elif status == "Без данни":
                tag = "status-warn"
            else:
                tag = "status-neutral"
            url_item = self.tree.insert("", "end", iid=url, text=url, values=(status,), tags=(tag,), open=True)
            for sel in sorted(selectors):
                self.tree.insert(url_item, "end", text=sel, values=("",))
                selector_count += 1
        self.count_var.set(f"{len(self.tracker.tracked)} URL / {selector_count} селектори")

    def update_data_display(self) -> None:
        self.data_text.delete("1.0", tk.END)
        if self.data_store:
            self.data_text.insert(tk.END, json.dumps(self.data_store, ensure_ascii=False, indent=4))
        else:
            self.data_text.insert(tk.END, "Все още няма събрани данни.")

    def set_activity(self, running: bool, message: str) -> None:
        self._status_animating = running
        self._status_base = message
        if running:
            self._status_phase = 0
            self.status_progress.start(10)
            self.animate_status()
        else:
            self.status_progress.stop()
            self.status_var.set(message)
            self.status_label.configure(foreground=self._status_pulse_colors[0])
            self.status_label.configure(foreground=self._status_pulse_colors[0])

    def animate_status(self) -> None:
        if not self._status_animating:
            return
        dots = "." * (self._status_phase % 4)
        self.status_var.set(f"{self._status_base}{dots}")
        pulse_color = self._status_pulse_colors[self._status_phase % 2]
        self.status_label.configure(foreground=pulse_color)
        self._status_phase += 1
        self.after(350, self.animate_status)

    def show_error_banner(self, message: str) -> None:
        self.error_var.set(message)
        if not self.error_frame.winfo_ismapped():
            self.error_frame.pack(fill="x", padx=12, pady=(0, 8))
        if self._error_after_id is not None:
            self.after_cancel(self._error_after_id)
        self._error_after_id = self.after(5000, self.hide_error_banner)

    def hide_error_banner(self) -> None:
        if self.error_frame.winfo_ismapped():
            self.error_frame.pack_forget()
        self._error_after_id = None

    def is_valid_url(self, url: str) -> bool:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    def add_tracked(self) -> None:
        url = self.get_entry_value(self.entry_url, self._url_placeholder)
        selector = self.get_entry_value(self.entry_selector, self._selector_placeholder)
        if not url or not selector:
            self.validation_var.set("Моля, попълнете URL и CSS селектор.")
            return
        if not self.is_valid_url(url):
            self.validation_var.set("Моля, въведете валиден URL (http/https).")
            return

        status = self.tracker.add(url, selector)
        self.clear_validation()
        if status == 0:
            self.log(f"Внимание: Селекторът '{selector}' вече съществува за {url}.")
        elif status == 1:
            self.log(f"Добавен нов URL: {url} с селектор '{selector}'.")
        elif status == 2:
            self.log(f"Добавен селектор '{selector}' към съществуващ URL {url}.")

        self.update_tracked_tree()
        self.apply_placeholder(self.entry_url, self._url_placeholder)
        self.apply_placeholder(self.entry_selector, self._selector_placeholder)

    def remove_selected(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Внимание", "Моля, изберете елемент за премахване.")
            return

        item = selected[0]
        parent = self.tree.parent(item)

        if parent == "":  # URL
            url = self.tree.item(item, "text")
            if messagebox.askyesno("Потвърждение", f"Премахване на URL {url} и всички негови селектори?"):
                self.tracker.remove_url(url)
                self.tree.delete(item)
                self.log(f"Премахнат URL: {url}")
        else:  # Селектор
            selector = self.tree.item(item, "text")
            url = self.tree.item(parent, "text")
            if messagebox.askyesno("Потвърждение", f"Премахване на селектор '{selector}' от {url}?"):
                self.tracker.remove_selector(url, selector)
                self.tree.delete(item)
                self.log(f"Премахнат селектор '{selector}' от {url}")
                if not self.tree.get_children(parent):
                    self.tree.delete(parent)

        self.update_tracked_tree()

    def check_queue(self) -> None:
        try:
            while True:
                item = self.q.get_nowait()
                if isinstance(item, str):
                    self.log(item)
                    if "Грешка" in item:
                        self.show_error_banner(item)
                elif isinstance(item, tuple) and len(item) == 2:
                    timestamp, data = item
                    self.data_store[timestamp] = data
                    self.update_data_display()
                    self.last_run_var.set(f"Последно извличане: {timestamp}")
                    for url in self.tracker.tracked.keys():
                        if url in self.tracker.last_errors:
                            self.url_status[url] = "Грешка"
                        elif data.get(url) is None:
                            self.url_status[url] = "Без данни"
                        else:
                            self.url_status[url] = "OK"
                    self.update_tracked_tree()
                elif isinstance(item, tuple) and len(item) == 3 and item[0] == "status":
                    _, running, message = item
                    self.set_activity(running, message)
        except queue.Empty:
            pass
        self.after(200, self.check_queue)

    def single_extract(self) -> None:
        timestamp = datetime.datetime.now().isoformat()
        self.q.put(f"[{timestamp}] Ръчно извличане започна...")
        try:
            data = asyncio.run(self.tracker.extract_all_async())
            self.q.put((timestamp, data))
            if self.tracker.last_errors:
                for url, error in self.tracker.last_errors.items():
                    self.q.put(f"[{timestamp}] Грешка при {url}: {error}")
            self.q.put(f"[{timestamp}] Ръчно извличане завърши успешно.")
        except Exception as e:
            self.q.put(f"[{timestamp}] Грешка при ръчно извличане: {e}")
        finally:
            self.q.put(("status", False, "Готово"))
            self.manual_running = False

    def manual_extract(self) -> None:
        if self.running or self.manual_running:
            messagebox.showinfo("Информация", "Извличането вече се изпълнява.")
            return
        if not self.tracker.tracked:
            messagebox.showinfo("Информация", "Няма добавени URL-и за извличане.")
            return
        self.manual_running = True
        self.set_activity(True, "Ръчно извличане")
        threading.Thread(target=self.single_extract, daemon=True).start()

    def periodic_task(self, interval: int) -> None:
        while self.running:
            timestamp = datetime.datetime.now().isoformat()
            self.q.put(f"[{timestamp}] Периодично извличане започна...")
            try:
                data = asyncio.run(self.tracker.extract_all_async())
                self.q.put((timestamp, data))
                if self.tracker.last_errors:
                    for url, error in self.tracker.last_errors.items():
                        self.q.put(f"[{timestamp}] Грешка при {url}: {error}")
                self.q.put(f"[{timestamp}] Периодично извличане завърши.")
            except Exception as e:
                self.q.put(f"[{timestamp}] Грешка при периодично извличане: {e}")
            time.sleep(interval)

    def start_periodic(self) -> None:
        if self.running:
            return
        if self.manual_running:
            messagebox.showinfo("Информация", "Ръчното извличане работи в момента.")
            return
        if not self.tracker.tracked:
            messagebox.showinfo("Информация", "Добавете поне един URL преди да стартирате периодичното извличане.")
            return

        try:
            interval = int(self.entry_interval.get())
            if interval <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Грешка", "Моля, въведете положително цяло число за интервал.")
            return

        self.running = True
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.set_activity(True, "Периодично извличане")
        self.thread = threading.Thread(target=self.periodic_task, args=(interval,), daemon=True)
        self.thread.start()
        self.log(f"Периодично извличане стартирано с интервал {interval} секунди.")

    def stop_periodic(self) -> None:
        self.running = False
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        if not self.manual_running:
            self.set_activity(False, "Готово")
        self.log("Периодичното извличане е спряно.")

    def save_json(self) -> None:
        file = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON файлове", "*.json")])
        if file:
            try:
                self.tracker.save_to_json(self.data_store, file)
                self.log(f"Данните са записани в JSON: {file}")
            except Exception as e:
                messagebox.showerror("Грешка", f"Неуспешно записване: {e}")

    def save_csv(self) -> None:
        file = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV файлове", "*.csv")])
        if file:
            try:
                self.tracker.save_to_csv(self.data_store, file)
                self.log(f"Данните са записани в CSV: {file}")
            except Exception as e:
                messagebox.showerror("Грешка", f"Неуспешно записване: {e}")

    def load_json(self) -> None:
        file = filedialog.askopenfilename(filetypes=[("JSON файлове", "*.json")])
        if file:
            try:
                self.data_store = self.tracker.load_from_json(file)
                self.update_data_display()
                self.log(f"Данните са заредени от: {file}")
            except Exception as e:
                messagebox.showerror("Грешка", f"Неуспешно зареждане: {e}")
