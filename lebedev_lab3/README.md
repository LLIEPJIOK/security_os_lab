# Отчет по лабораторной работе №3

_Автор: Лебедев Денис_

## Описание

Программа предназначена для архивации файлов и директорий с сохранением прав доступа на Windows и Linux. Запакованный архив представляет собой файл в формате `tar` с расширением `.perm`, поэтому его можно распаковать с помощью обычного архиватора. Информация о правах доступа сохраняется в файле `.acls` и сохраняется при переносе на разные устройства.

Структура:
```tree
lebedev_lab3/
├── acl/ # C# библиотека для работы с правами доступа на Windows
│   ├── acl/
│   │   ├── bin/
│   │   │   └── Release/
│   │   │       └── net8.0/
│   │   │           └── acl.dll # Скомпилированная библиотека
│   │   ├── Acl.cs # Исходный код библиотеки
│   │   └── acl.csproj # Проект библиотеки
│   └── acl.sln # Решение библиотеки
├── .gitignore
├── archive_manager.py # Логика архиватора
├── gui_app.py # GUI приложение
├── linux_acl_handler.py # Файл для работы с правами доступа на Linux
├── README.md
└── requirements.txt
```

## Начало работы

### Установка зависимостей

Для запуска программы необходимо установить зависимости:

- [python 3.12](https://www.python.org/downloads/)(на 3.14 не подтянулся tkinter)
- tkinter. Он входит в стандартную библиотеку python, но на линуксе может потребоваться отдельная установка `sudo apt install python3-tk`
- [.NET 8.0 SDK for Windows](https://dotnet.microsoft.com/en-us/download/dotnet/8.0)

### Создание venv

_Note: Применения прав может потребовать прав администратора. Поэтому рекомендуется использовать Powershell с правами администратора на Windows и sudo на Linux._

1. Создайте виртуальное окружение:

```bash
python -m venv .venv
```

2. Активируйте виртуальное окружение:

Для Windows PowerShell:

```powershell
.venv\Scripts\activate.ps1
```

Для Linux:

```bash
source .venv/bin/activate
```

3. Установите зависимости:

```bash
pip install -r requirements.txt
```

### Запуск программы

Для Windows:

```powershell
python gui_app.py
```

Для Linux:

```bash
sudo $(which python3) gui_app.py
```
