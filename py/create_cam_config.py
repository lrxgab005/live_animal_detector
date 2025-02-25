import tkinter as tk
import json
import config
import os
from typing import Dict


def create_config() -> None:

  def save_config() -> None:
    config_data: Dict[str, str] = {
        "USER": user_entry.get(),
        "PASSWORD": password_entry.get(),
        "HOST": host_entry.get(),
        "PORT": port_entry.get(),
        "CHANNEL": channel_entry.get()
    }
    file_name: str = file_name_entry.get()
    if not file_name.endswith('.json'):
      file_name += '.json'

    cam_config_path: str = os.path.join(config.CAM_CONFIG_PATH, file_name)
    with open(cam_config_path, 'w') as config_file:
      json.dump(config_data, config_file, indent=4)

    print("Configuration saved to:")
    print(cam_config_path)

    dialog.destroy()
    root.quit()

  root: tk.Tk = tk.Tk()
  root.withdraw()

  dialog: tk.Toplevel = tk.Toplevel(root)
  dialog.title("Camera Configuration")

  tk.Label(dialog, text="Config File Name:").grid(row=0, column=0)
  file_name_entry: tk.Entry = tk.Entry(dialog)
  file_name_entry.grid(row=0, column=1)

  tk.Label(dialog, text="Enter USER:").grid(row=1, column=0)
  user_entry: tk.Entry = tk.Entry(dialog)
  user_entry.grid(row=1, column=1)

  tk.Label(dialog, text="Enter PASSWORD:").grid(row=2, column=0)
  password_entry: tk.Entry = tk.Entry(dialog, show="*")
  password_entry.grid(row=2, column=1)

  tk.Label(dialog, text="Enter HOST:").grid(row=3, column=0)
  host_entry: tk.Entry = tk.Entry(dialog)
  host_entry.grid(row=3, column=1)

  tk.Label(dialog, text="Enter PORT:").grid(row=4, column=0)
  port_entry: tk.Entry = tk.Entry(dialog)
  port_entry.grid(row=4, column=1)

  tk.Label(dialog, text="Enter CHANNEL:").grid(row=5, column=0)
  channel_entry: tk.Entry = tk.Entry(dialog)
  channel_entry.grid(row=5, column=1)

  save_button: tk.Button = tk.Button(dialog, text="Save", command=save_config)
  save_button.grid(row=6, columnspan=2)

  dialog.mainloop()


if __name__ == "__main__":
  create_config()
