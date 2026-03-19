import FreeSimpleGUI as sg
from persistence.Persistence import *
from BaseUtils import *
from datetime import datetime, timedelta
from time import strftime
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMainWindow
from utils.RedisUtils import *
# from utils.ReportUtils import ReportBuilder
# import threading
import textwrap

# from dateutil.relativedelta import relativedelta

aWindowIsInProgress: bool = False


# ****************************************** Start - Utility Methods ************************************************

def progressBar(message: str = "Progress status of your instruction", theme: str = "DarkBlue16"):
    sg.theme(theme)
    layout = [[sg.Text(message)],
              [sg.ProgressBar(1000, orientation='h', size=(20, 20), key='progbar')],
              [sg.Cancel()]]

    window = sg.Window('Working...', layout, keep_on_top=True, finalize=True, modal=True, force_toplevel=True,
                       disable_minimize=True, grab_anywhere=False, disable_close=True)
    for i in range(1000):
        event, values = window.read(timeout=1)
        if event == 'Cancel' or event == sg.WIN_CLOSED:
            break
        window['progbar'].update_bar(i + 1)
    window.close()


def showApplicationStartingScreen(textToShow: str = "Application is starting", auto_close_duration: int = 1):
    sg.theme('DarkBlue15')
    textToShow = f"\n{textToShow}\n"
    # layout = [
    #             [sg.Text(textToShow, size=(len(textToShow) + 5, 1), font=16)],
    #         ]
    # #
    # window = sg.Window(textToShow, layout, modal = True, keep_on_top=True, finalize=True, disable_minimize=True, force_toplevel=True, grab_anywhere=False, disable_close=True, auto_close_duration=auto_close_duration)
    # window.read(timeout=auto_close_duration)
    # time.sleep(auto_close_duration)
    # window.close()
    # return None
    return sg.popup(textToShow, title=textToShow, button_type=sg.POPUP_BUTTONS_NO_BUTTONS,
                    auto_close=True,
                    auto_close_duration=auto_close_duration, non_blocking=True, line_width=len(textToShow) + 25,
                    font=('Helvetica', 25, "bold"),
                    no_titlebar=True, grab_anywhere=False,
                    # keep_on_top=True, location=(None, None), any_key_closes=False, image=None, modal=True)
                    keep_on_top=True, any_key_closes=False, modal=True)


# def showMessage(textToShow : str = "Type Input", blocking : bool = True, auto_close_duration : int = 2):
#     sg.theme('DarkBlue15')
#     textToShow = f"\n{textToShow}\n"
#     sg.popup_auto_close(textToShow, auto_close_duration=auto_close_duration, font=("Helvetica",25, "bold"), line_width=len(textToShow) + 5, no_titlebar=True, button_type=sg.POPUP_BUTTONS_NO_BUTTONS, keep_on_top=True, modal = True, grab_anywhere=False, non_blocking=not blocking)

def showMessage(textToShow: str = "A Message", theme: str = 'DarkBlue15', auto_close_duration: int = 2):
    """Display a message with auto-close timer and OK button, matching DarkBlue15 style."""
    sg.theme(theme)

    # Edge Case: Empty or None textToShow
    if not textToShow or textToShow.isspace():
        textToShow = "No message provided"
    textToShow = f"\n{textToShow}\n"

    # Font: Use Helvetica directly; PySimpleGUI falls back to system default (e.g., Arial) if unavailable
    font = ("Helvetica", 16, "bold")
    button_font = ("Helvetica", 16)  # Smaller font for OK button

    # Edge Case: Invalid auto_close_duration
    if not isinstance(auto_close_duration, int) or auto_close_duration <= 0:
        # print(f"Invalid auto_close_duration ({auto_close_duration}), using default of 1 second")
        auto_close_duration = 1

    # Edge Case: Long text wrapping
    max_line_length = 60  # Prevent overly wide windows
    if len(textToShow) > max_line_length:
        textToShow = "\n" + "\n".join(textwrap.wrap(textToShow.strip(), width=max_line_length)) + "\n"
    text_width = max(len(line) for line in textToShow.split("\n")) + 5

    layout = [
        [sg.Text(textToShow, key='-TEXT-', font=font, justification="center", size=(text_width, None))],
        [sg.Button("OK", key="-OK-", size=(10, 1), font=button_font)]
    ]

    window = sg.Window(
        "",
        layout,
        no_titlebar=True,
        keep_on_top=True,
        modal=True,
        grab_anywhere=False,
        finalize=True,
        return_keyboard_events=True,
        element_justification="center",
        margins=(10, 10)
    )

    # Focus text element and bind Enter to OK button
    try:
        window['-TEXT-'].set_focus()
        # print("Text element focused")
    except Exception as e:
        # print(f"Focus failed: {e}")
        window.bring_to_front()  # Fallback

    window['-OK-'].bind("<Return>", "_Enter")

    # Blocking mode: Wait for auto_close_duration, OK, or window close
    event, values = window.read(timeout=auto_close_duration * 1000)
    # print(f"Event: {event}")  # Debug
    window.close()

    # NOTE: COMMENTED OUT BECAUSE threading LIBRARY INTERFERES WITH PYSIDE6.
    # else:
    #     # Non-blocking mode: Thread for auto-close
    #     def close_window():
    #         try:
    #             event, values = window.read(timeout=auto_close_duration * 1000)
    #             # print(f"Non-blocking event: {event}")
    #             window.close()
    #         except Exception as e:
    #             # print(f"Non-blocking thread error: {e}")
    #             pass
    #
    #     try:
    #         threading.Thread(target=close_window, daemon=True).start()
    #     except Exception as e:
    #         # print(f"Thread start failed: {e}")
    #         window.close()


# def getSimpleInput(textToShow : str = "Type Input", modal : bool = False):
#     sg.theme('LightBlue2')
#     inputReceived = sg.popup_get_text(
#         f'{textToShow}', modal=modal, keep_on_top=True)
#     if inputReceived is not None:
#         inputReceived = inputReceived.strip()
#     else:
#         inputReceived = ''
#     return inputReceived

def getSimpleInput(textToShow: str = "Type Input", modal: bool = False):
    sg.theme('LightBlue2')

    layout = [
        [sg.Text(textToShow, font=16, pad=(10, 10))],
        [sg.InputText(key='-INPUT-', font=16, size=(30, 1))],
        [sg.Button("OK", key="-OK-", size=(10, 1)), sg.Button("Cancel", key="-CANCEL-", size=(10, 1))]
    ]

    window = sg.Window(
        "Input",
        layout,
        modal=modal,
        keep_on_top=True,
        grab_anywhere=False,
        finalize=True,
        return_keyboard_events=True
    )

    try:
        window['-INPUT-'].set_focus()  # Set focus to input field
        window['-INPUT-'].bind("<Return>", "_Enter")  # Bind Enter key to input field
    except:
        window.bring_to_front()

    while True:
        event, values = window.read()
        if event in ("-OK-", "-INPUT-_Enter"):  # OK button or Enter key
            inputReceived = values['-INPUT-']
            if inputReceived is not None:
                inputReceived = inputReceived.strip()
            else:
                inputReceived = ''
            break
        elif event in ("-CANCEL-", sg.WIN_CLOSED):  # Cancel button or window close
            inputReceived = ''
            break

    window.close()
    return inputReceived


def getAssuredInputTillCancel(currentUser: str, currentRole: str = "Supervisor", textToShow: str = "Type Input",
                              confirmationStart: str = "Value", modal: bool = True):
    global aWindowIsInProgress
    submitted: bool = False
    inputValue: str | None = None

    if aWindowIsInProgress:
        return submitted, inputValue

    sg.theme('DarkBlue15')
    aWindowIsInProgress = True

    layout = [
        [sg.Text(textToShow, size=(30, 1), font=16), sg.InputText(key='-inputReceived-', font=16)],
        [sg.Button("Submit"), sg.Button("Cancel")]
    ]

    window = sg.Window(textToShow, layout, modal=modal, keep_on_top=True, finalize=True, disable_minimize=True,
                       force_toplevel=True, grab_anywhere=False, disable_close=True)
    window['-inputReceived-'].set_focus()
    window['-inputReceived-'].bind("<Return>", "_Enter")

    while True:
        event, values = window.read()
        if (event == 'Cancel') or (event == sg.WIN_CLOSED):
            submitted = False
            inputValue = None
            showErrorMessage("Cancelling this operation", auto_close_duration=2)
            break
        else:
            if event in ("Submit", "-inputReceived-_Enter"):
                submitted = True
                # print('Clicked Submit')
                inputValue = values['-inputReceived-'].strip()
                if len(inputValue) == 0:
                    submitted = False
                    inputValue = None
                    showErrorMessage("No value provided. Please re-enter and submit.")
                    sg.theme('DarkBlue15')
                else:
                    confirmationMessage = f"{confirmationStart} provided is {inputValue}. Are you sure to proceed ahead ?"
                    confirmed: str = getConfirmation(confirmationMessage)
                    if confirmed.upper() == 'OK':
                        break
                    else:
                        submitted = False
                        inputValue = None
                        showErrorMessage("Please re-enter and submit.", auto_close_duration=2)
                        sg.theme('DarkBlue15')
    aWindowIsInProgress = False
    window.close()
    return submitted, inputValue


# def getConfirmation(message : str, question : str = "Please click OK to confirm, Cancel to re-enter", title : str = "Confirm Input", theme : str = "LightBlue", modal : bool = True):
#     sg.theme(theme)
#     response = sg.popup_ok_cancel(message, question, title=title, font = 24, modal = modal, keep_on_top=True, grab_anywhere=False)
#     if response is not None:
#         response = response.strip()
#     else:
#         response = "Cancel"
#     return response

def getConfirmation(message: str, question: str = "Please click OK to confirm, Cancel to re-enter",
                    title: str = "Confirm Input", theme: str = "LightBlue", modal: bool = True):
    sg.theme(theme)

    layout = [
        [sg.Text(message, font=16)],
        [sg.Text(question, font=16)],
        [sg.Button("OK", size=(10, 1), key="-OK-"), sg.Button("Cancel", size=(10, 1), key="-CANCEL-")]
    ]

    window = sg.Window(
        title,
        layout,
        modal=modal,
        keep_on_top=True,
        grab_anywhere=False,
        finalize=True,
        return_keyboard_events=True
    )

    try:
        window["-OK-"].set_focus()  # Set focus to OK button
        window["-OK-"].bind("<Return>", "_Enter")  # Bind Enter key to OK button
    except:
        window.bring_to_front()

    while True:
        event, values = window.read()
        if event in ("-OK-", "-OK-_Enter") or event == sg.WIN_CLOSED:
            response = "OK"
            break
        elif (event == "-CANCEL-") or (event == sg.WIN_CLOSED):
            response = "Cancel"
            break

    window.close()

    if response is not None:
        response = response.strip()
    else:
        response = "Cancel"

    return response


# def showErrorMessage(errorMessage : str, auto_close_duration=3):
#     sg.theme('DarkRed2')
#     sg.popup_auto_close(errorMessage, auto_close_duration=auto_close_duration, font=24, line_width=len(errorMessage) if errorMessage is not None else 25, keep_on_top=True, modal = True, grab_anywhere=False)

def showErrorMessage(errorMessage: str, auto_close_duration: int = 3, theme: str = 'DarkRed2'):
    """Display an error message with auto-close timer and focused OK button in DarkRed2 theme."""
    sg.theme(theme)

    # Edge Case: Empty or None errorMessage
    if not errorMessage or errorMessage.isspace():
        errorMessage = "No error message provided"

    # Font: Use Helvetica, size 16
    font = ("Helvetica", 16)
    button_font = ("Helvetica", 16)

    # Edge Case: Invalid auto_close_duration
    if not isinstance(auto_close_duration, int) or auto_close_duration <= 0:
        auto_close_duration = 3

    # Edge Case: Long text wrapping
    max_line_length = 60
    if len(errorMessage) > max_line_length:
        errorMessage = "\n" + "\n".join(textwrap.wrap(errorMessage, width=max_line_length)) + "\n"
    text_width = max(len(line) for line in errorMessage.split("\n")) if errorMessage else 25

    layout = [
        [sg.Text(errorMessage, key='-TEXT-', font=font, justification="center", size=(text_width, None))],
        [sg.Button("OK", key="-OK-", size=(10, 1), font=button_font)]
    ]

    window = sg.Window(
        "",
        layout,
        no_titlebar=True,
        keep_on_top=True,
        modal=True,
        grab_anywhere=False,
        finalize=True,
        return_keyboard_events=False,  # Disable keyboard events to prevent Enter propagation
        element_justification="center",
        margins=(10, 10)
    )

    # Focus OK button and bind Enter key
    try:
        window['-OK-'].set_focus()
    except Exception:
        window.bring_to_front()

    window['-OK-'].bind("<Return>", "_Enter")

    # Introduce a short delay to ensure window is fully rendered
    # sg.OneLineProgressMeter('Rendering', 1, 1, 'key', no_titlebar=True, no_button=True, grab_anywhere=False,
    #                         keep_on_top=True)

    # Event loop: Wait for OK button or timeout
    start_time = time.time()
    while True:
        event, values = window.read(timeout=100)  # Poll every 100ms
        if event in ("-OK-", "-OK-_Enter") or event == sg.WIN_CLOSED:
            break
        if time.time() - start_time >= auto_close_duration:
            break

    window.close()


# def flashSimpleMessage(simpleMessage : str = "A simple message", auto_close_duration=2, line_width : int = 40):
#     sg.theme('DarkBlue15')
#     sg.popup_auto_close(simpleMessage, auto_close_duration=auto_close_duration, font=24, line_width=line_width, keep_on_top=True, modal = True, grab_anywhere=False)

def flashSimpleMessage(simpleMessage: str = "A simple message", auto_close_duration: int = 2, line_width: int = 40,
                       theme: str = 'DarkBlue15'):
    """Display a simple message with auto-close timer and focused OK button in DarkBlue15 theme."""
    sg.theme(theme)

    # Edge Case: Empty or None simpleMessage
    if not simpleMessage or simpleMessage.isspace():
        simpleMessage = "No message provided"

    # Edge Case: Invalid line_width
    if not isinstance(line_width, int) or line_width < 10:
        # print(f"Invalid line_width ({line_width}), using default of 40")
        line_width = 40

    # Font: Use Helvetica, size 24; PySimpleGUI falls back to system default if unavailable
    font = ("Helvetica", 16)
    button_font = ("Helvetica", 16)  # Smaller font for OK button

    # Edge Case: Invalid auto_close_duration
    if not isinstance(auto_close_duration, int) or auto_close_duration <= 0:
        # print(f"Invalid auto_close_duration ({auto_close_duration}), using default of 1 second")
        auto_close_duration = 1

    # Edge Case: Long text wrapping
    if len(simpleMessage) > line_width:
        simpleMessage = "\n" + "\n".join(textwrap.wrap(simpleMessage, width=line_width)) + "\n"
    text_width = max(len(line) for line in simpleMessage.split("\n")) if simpleMessage else line_width

    layout = [
        [sg.Text(simpleMessage, key='-TEXT-', font=font, justification="center", size=(text_width, None))],
        [sg.Button("OK", key="-OK-", size=(10, 1), font=button_font)]
    ]

    window = sg.Window(
        "",
        layout,
        no_titlebar=True,
        keep_on_top=True,
        modal=True,
        grab_anywhere=False,
        finalize=True,
        return_keyboard_events=True,
        element_justification="center",
        margins=(10, 10)
    )

    # Focus OK button and bind Enter key
    try:
        window['-OK-'].set_focus()
        # print("OK button focused")  # Debug
    except Exception as e:
        # print(f"Focus failed: {e}")
        window.bring_to_front()  # Fallback

    window['-OK-'].bind("<Return>", "_Enter")

    # Blocking mode: Wait for auto_close_duration, OK, or window close
    event, values = window.read(timeout=auto_close_duration * 1000)
    # print(f"Event: {event}")  # Debug
    window.close()


def displayScrollableColumnNoHeader(listOfSgText: list, title: str = "Scrollable Data", buttonName: str = "OK",
                                    size=(None, None)):
    sg.theme("DarkBlue16")
    layout = [
        [sg.Column(listOfSgText, scrollable=True, vertical_scroll_only=True)],
        [sg.Button(buttonName)]
    ]
    # window = sg.Window(title=title, layout=layout, size=size, keep_on_top=True, finalize=True, modal=True, disable_minimize=True, force_toplevel=True)
    window = sg.Window(title=title, layout=layout, size=size, keep_on_top=True, finalize=True, modal=True,
                       disable_minimize=True, grab_anywhere=False)
    toBeSent = False
    while True:
        event, values = window.read()
        if event == 'Send':
            toBeSent = True
        break
    window.close()
    return toBeSent


def displayScrollableColumnWithHeader(header: str, contentToBeDisplayed: str, title: str = "Scrollable Data",
                                      buttonName: str = "Save", size=(None, None)):
    sg.theme("DarkBlue16")
    layout = [[sg.Text(header, font=("Courier New", 12, "bold"))],
              [sg.Column([[sg.Text(contentToBeDisplayed, font=("Courier New", 12))]], scrollable=True,
                         vertical_scroll_only=True, size=size)],
              [sg.Button(buttonName)],
              ]
    # window = sg.Window(title=title, layout=layout, modal = True, keep_on_top=True, finalize=True, disable_minimize=True, force_toplevel=True)
    window = sg.Window(title=title, layout=layout, modal=True, keep_on_top=True, finalize=True, disable_minimize=True,
                       grab_anywhere=False)
    toBeActed = False
    while True:
        event, values = window.read()
        if event == buttonName:
            toBeActed = True
        break
    window.close()
    return toBeActed


# def getJustPassword(textToShow : str = "Enter passsword", modal : bool = False):
#     sg.theme('LightBlue2')
#     password = sg.popup_get_text(
#         f'{textToShow}', password_char='*', modal = True, keep_on_top=True)
#     if password is not None:
#         password = password.strip()
#     else:
#         password = ''
#     return password

def getJustPassword(textToShow: str = "Enter password", modal: bool = False):
    """Prompt for a password with a focused input field in LightBlue2 theme."""
    sg.theme('LightBlue2')

    # Edge Case: Empty or None textToShow
    if not textToShow or textToShow.isspace():
        textToShow = "Enter password"

    # Font: Use Helvetica, size 16 for consistency with getSimpleInput
    font = ("Helvetica", 16)
    button_font = ("Helvetica", 16)

    # Edge Case: Long textToShow
    max_line_length = 60  # Prevent overly wide prompts
    if len(textToShow) > max_line_length:
        textToShow = "\n".join(textwrap.wrap(textToShow, width=max_line_length))
    text_width = max(len(line) for line in textToShow.split("\n")) if textToShow else 20

    layout = [
        [sg.Text(textToShow, key='-TEXT-', font=font, justification="center", size=(text_width, None))],
        [sg.InputText(key='-PASSWORD-', font=font, password_char='*', size=(30, 1))],
        [sg.Button("OK", key="-OK-", size=(10, 1), font=button_font),
         sg.Button("Cancel", key="-CANCEL-", size=(10, 1), font=button_font)]
    ]

    window = sg.Window(
        "Password Input",
        layout,
        modal=True,  # Original uses modal=True, overriding parameter for consistency
        keep_on_top=True,
        grab_anywhere=False,
        finalize=True,
        return_keyboard_events=True,
        element_justification="center",
        margins=(10, 10)
    )

    # Focus password input field and bind Enter key
    try:
        window['-PASSWORD-'].set_focus()
        # print("Password input focused")  # Debug
    except Exception as e:
        # print(f"Focus failed: {e}")
        window.bring_to_front()  # Fallback

    window['-PASSWORD-'].bind("<Return>", "_Enter")

    while True:
        event, values = window.read()
        # print(f"Event: {event}")  # Debug
        if event in ("-OK-", "-PASSWORD-_Enter"):  # OK button or Enter key
            password = values['-PASSWORD-']
            if password is not None:
                password = password.strip()
            else:
                password = ''
            break
        elif event in ("-CANCEL-", sg.WIN_CLOSED):  # Cancel button or window close
            password = ''
            break

    window.close()
    return password


# ****************************************** End - Utility Methods ************************************************

# ****************************************** Begin - User Management Methods ****************************************

def createAccount(currentUser: str, currentRole: str = "Supervisor", modal: bool = True):
    global aWindowIsInProgress
    username: str = ''
    password: str = ''
    email: str = ''
    mobile: str = ''
    role: str = 'Operator'
    firstname: str = ''
    middlename: str = ''
    lastname: str = ''
    submitted: bool = False
    successfullyInserted: bool = False
    nExistingRecords: int = 0

    if aWindowIsInProgress:
        # flashSimpleMessage("A menu operation is already in progress", auto_close_duration=2)
        return submitted, successfullyInserted, nExistingRecords, username, firstname, middlename, lastname, password, email, mobile, role

    aWindowIsInProgress = True

    db_name = getDatabaseName()
    userData = getIdAndUsernamesAndPasswordsAndRolesForActiveUsers(db_name)
    currentUsernames = []
    for aRecord in userData:
        currentUsernames.append(aRecord[1])

    sg.theme('LightBlue3')
    layout = [
        [sg.Text("Create Username", size=(20, 1), font=16), sg.InputText(key='-username-', font=16)],
        [sg.Text("First Name", size=(20, 1), font=16), sg.InputText(key='-firstname-', font=16)],
        [sg.Text("Middle Name", size=(20, 1), font=16), sg.InputText(key='-middlename-', font=16)],
        [sg.Text("Last Name", size=(20, 1), font=16), sg.InputText(key='-lastname-', font=16)],
        [sg.Text("Create Password", size=(20, 1), font=16), sg.InputText(key='-password-', font=16, password_char='*')],
        [sg.Text("Re-enter Password", size=(20, 1), font=16),
         sg.InputText(key='-password1-', font=16, password_char='*')],
        [sg.Text("E-mail", size=(20, 1), font=16), sg.InputText(key='-email-', font=16)],
        [sg.Text("Mobile", size=(20, 1), font=16), sg.InputText(key='-mobile-', font=16)],
        [sg.Text("Role", size=(20, 1), font=16),
         sg.Combo(values=allowed_roles[2:], default_value=allowed_roles[2], font=16,
                  k='-role-')] if currentRole == "Supervisor" else
        [sg.Text("Role", size=(20, 1), font=16),
         sg.Combo(values=allowed_roles, default_value=allowed_roles[2], font=16, k='-role-')],
        [sg.Button("Submit"), sg.Button("Cancel")]
    ]

    window = sg.Window("Create New Account", layout, modal=True, keep_on_top=True, finalize=True, disable_minimize=True,
                       grab_anywhere=False, disable_close=True)
    window['-username-'].set_focus()
    window['-role-'].bind("<Return>", "_Enter")

    while True:
        event, values = window.read()
        username: str = ''
        password: str = ''
        email: str = ''
        mobile: str = ''
        role: str = 'Operator'
        firstname: str = ''
        middlename: str = ''
        lastname: str = ''
        submitted: bool = False
        successfullyInserted: bool = False
        nExistingRecords: int = 0
        if event == 'Cancel' or event == sg.WIN_CLOSED:
            submitted = False
            showErrorMessage("Cancelling user addition.", auto_close_duration=2)
            break
        else:
            if event in ("Submit", "-role-_Enter"):
                submitted = True
                # print('Clicked Submit')
                username = values['-username-'].strip()
                firstname = values['-firstname-'].strip()
                middlename = values['-middlename-'].strip()
                lastname = values['-lastname-'].strip()
                password = values['-password-'].strip()
                password1 = values['-password1-'].strip()
                email = values['-email-'].strip()
                mobile = values['-mobile-'].strip()
                role = values['-role-'].strip()
                if username in currentUsernames:
                    showErrorMessage(f"Username {username} already exists. Please change and submit.")
                    sg.theme('LightBlue3')
                    username = ''
                    password = ''
                    email = ''
                    mobile = ''
                    role = 'Operator'
                    firstname = ''
                    middlename = ''
                    lastname = ''
                    submitted = False
                    successfullyInserted = False
                    nExistingRecords = 0
                elif len(username) < 5:
                    username = ''
                    password = ''
                    email = ''
                    mobile = ''
                    role = 'Operator'
                    firstname = ''
                    middlename = ''
                    lastname = ''
                    submitted = False
                    successfullyInserted = False
                    nExistingRecords = 0
                    showErrorMessage("Username has to be at least 5 characters. Please re-enter and submit.")
                    sg.theme('LightBlue3')
                elif password != password1:
                    username = ''
                    password = ''
                    email = ''
                    mobile = ''
                    role = 'Operator'
                    firstname = ''
                    middlename = ''
                    lastname = ''
                    submitted = False
                    successfullyInserted = False
                    nExistingRecords = 0
                    showErrorMessage("The 2 password entries do not match. Please re-enter and submit.")
                    sg.theme('LightBlue3')
                elif len(password) < 6:
                    username = ''
                    password = ''
                    email = ''
                    mobile = ''
                    role = 'Operator'
                    firstname = ''
                    middlename = ''
                    lastname = ''
                    submitted = False
                    successfullyInserted = False
                    nExistingRecords = 0
                    showErrorMessage("The password must have at least 6 characters.")
                    sg.theme('LightBlue3')
                elif len(firstname) == 0 and len(middlename) == 0 and len(lastname) == 0:
                    username = ''
                    password = ''
                    email = ''
                    mobile = ''
                    role = 'Operator'
                    firstname = ''
                    middlename = ''
                    lastname = ''
                    submitted = False
                    successfullyInserted = False
                    nExistingRecords = 0
                    showErrorMessage("At least 1 of first, middle, or last name is needed.")
                    sg.theme('LightBlue3')
                else:
                    confirmationMessage = f"Username : {username}\nFirst Name : {firstname}\nMiddle Name : {middlename}\nLast Name: {lastname}\nemail : {email}\nMobile : {mobile}\nRole : {role}"
                    confirmed: str = getConfirmation(confirmationMessage)
                    if confirmed.upper() == 'OK':
                        try:
                            db_name = getDatabaseName()
                            successfullyInserted, nExistingRecords = insertNewUser(db_name=db_name, username=username,
                                                                                   password=password,
                                                                                   first_name=firstname,
                                                                                   middle_name=middlename,
                                                                                   last_name=lastname, role_name=role,
                                                                                   email=email, mobile=mobile)
                            if successfullyInserted:
                                try:
                                    # insertAuditRecord(db_name=db_name, action=ADDED_NEW_USER, user=currentUser, role=currentRole,
                                    #                   remarks=f"Created user {username} with role {role}")
                                    progressBar(message="Creating newwidgets account...")
                                except:
                                    showErrorMessage(
                                        "Account could not be created. Likely reason is a database access problem.")
                                    sg.theme('LightBlue3')
                            elif nExistingRecords > 0:
                                try:
                                    showErrorMessage(
                                        "Account could not be created. User id already exists")
                                    # insertAuditRecord(db_name=db_name, action=ADDED_NEW_USER, user=currentUser, role=currentRole,
                                    #                   remarks=f"Could not create user {username} with role {role}")
                                    sg.theme('LightBlue3')
                                except:
                                    pass
                        except:
                            username = ''
                            password = ''
                            email = ''
                            mobile = ''
                            role = 'Operator'
                            firstname = ''
                            middlename = ''
                            lastname = ''
                            submitted = False
                            successfullyInserted = False
                            nExistingRecords = 0
                            showErrorMessage(
                                "Account could not be created. Likely reason is a database access problem.")
                            sg.theme('LightBlue3')
                        break
                    else:
                        username = ''
                        password = ''
                        email = ''
                        mobile = ''
                        role = 'Operator'
                        firstname = ''
                        middlename = ''
                        lastname = ''
                        submitted = False
                        successfullyInserted = False
                        nExistingRecords = 0
                        showErrorMessage("Please re-enter / re-check and submit.")
                        sg.theme('LightBlue3')
    # print('Exiting while True')
    aWindowIsInProgress = False
    window.close()
    return submitted, successfullyInserted, nExistingRecords, username, firstname, middlename, lastname, password, email, mobile, role


def login(modal: bool = True):
    global aWindowIsInProgress
    aWindowIsInProgress = False

    db_name = getDatabaseName()
    userData = getIdAndUsernamesAndPasswordsAndRolesForActiveUsers(db_name)
    printLight(userData)
    validUsernames = []
    for aRecord in userData:
        validUsernames.append(aRecord[1])
    username: str = ''
    password: str = ''
    rolename: str = ''
    submitted: bool = False
    successfullyLoggedIn: bool = False
    sg.theme("LightBlue2")
    if len(validUsernames) == 0:
        showErrorMessage("No users configured in database", auto_close_duration=5)
        # submitted, successfullyInserted, nExistingRecords, username, firstname, middlename, lastname, password, email, mobile, role = createAccount(currentUser, currentRole=allowed_roles[0])
        return submitted, successfullyLoggedIn, username, password, rolename
    else:
        layout = [
            # [sg.Text("Username", size =(15, 1), font=16),sg.InputText(key='-username-', font=16)],
            [sg.Text("Username", size=(20, 1), font=16),
             sg.Combo(values=validUsernames, default_value=validUsernames[0] if len(validUsernames) > 0 else '',
                      font=16, readonly=True, k='-username-')],
            [sg.Text("Password", size=(20, 1), font=16), sg.InputText(key='-password-', password_char='*', font=16)],
            [sg.Button('Login'), sg.Button('Cancel')]
        ]

        aWindowIsInProgress = True

        window = sg.Window(f"Login Screen", layout, return_keyboard_events=True, modal=True, keep_on_top=True,
                           finalize=True, disable_minimize=True, grab_anywhere=False, disable_close=True)
        window['-password-'].set_focus()
        window['-password-'].bind("<Return>", "_Enter")

        while True and aWindowIsInProgress:
            event, values = window.read()
            # print(f"Event: {event}")  # Debug: Print every event
            if event == "Cancel" or event == sg.WIN_CLOSED:
                username: str = ''
                password: str = ''
                rolename: str = ''
                submitted = True
                successfullyLoggedIn = False
                showErrorMessage("Cancelling login. The system will exit.")
                break
            else:
                if event in ("Login", "-password-_Enter"):
                    submitted = True
                    username = values['-username-']
                    password = values['-password-']
                    index = -1
                    for i, aUsername in enumerate(validUsernames):
                        if aUsername == username:
                            index = i
                            break
                    if index != -1:
                        if password == userData[index][2]:
                            rolename = userData[index][3]
                            successfullyLoggedIn = True
                        else:
                            username: str = ''
                            password: str = ''
                            rolename: str = ''
                            submitted = False
                            successfullyLoggedIn = False
                    if successfullyLoggedIn:
                        try:
                            flashSimpleMessage(f"Welcome, {username} ! You are logging in at {getCurrentTime()}",
                                               auto_close_duration=4)
                            sg.theme("LightBlue2")
                            # insertAuditRecord(db_name=db_name, action=LOGGED_IN, user=username, role=rolename, remarks=f"Successfully logged in")
                        except:
                            pass
                    else:
                        try:
                            showErrorMessage(
                                "Incorrect login credentials. The system allows upto 5 consecutive unsuccessful login attempts.")
                            # insertAuditRecord(db_name=db_name, action=LOGGED_IN, user=username, role=rolename,
                            #                   remarks=f"Could not log into system due to wrong password")
                            sg.theme("LightBlue2")
                        except:
                            pass
                        username: str = ''
                        password: str = ''
                        rolename: str = ''
                        submitted = False
                        successfullyLoggedIn = False
                    break
        window.close()
    aWindowIsInProgress = False
    return submitted, successfullyLoggedIn, username, password, rolename


def changePasswordForSelf(currentUser: str, currentRole: str, modal: bool = True):
    global aWindowIsInProgress
    password1: str = ''
    password2: str = ''
    submitted: bool = False

    if aWindowIsInProgress:
        # flashSimpleMessage("A menu operation is already in progress", auto_close_duration=2)
        return submitted, currentUser, password1

    db_name = getDatabaseName()
    userData = getIdAndUsernamesAndPasswordsAndRolesForActiveUsers(db_name)
    aWindowIsInProgress = True

    currentPassword = None
    if currentUser is not None:
        for aRecord in userData:
            if aRecord[1] == currentUser:
                currentPassword = aRecord[2]
                break
    sg.theme('LightBlue2')
    layout = [
        [sg.Text("Current Password", size=(20, 1), font=16),
         sg.InputText(key='-currentPassword-', font=16, password_char='*')],
        [sg.Text("Enter New Password", size=(20, 1), font=16),
         sg.InputText(key='-newpassword1-', font=16, password_char='*')],
        [sg.Text("Re-enter New Password", size=(20, 1), font=16),
         sg.InputText(key='-newpassword2-', font=16, password_char='*')],
        [sg.Button("Submit"), sg.Button("Cancel")]
    ]

    window = sg.Window(f"Change Password for user : {currentUser}", layout, modal=True, keep_on_top=True, finalize=True,
                       disable_minimize=True, grab_anywhere=False, disable_close=True)
    window['-currentPassword-'].set_focus()
    window['-newpassword2-'].bind("<Return>", "_Enter")

    while True:
        event, values = window.read()
        if event == 'Cancel' or event == sg.WIN_CLOSED:
            submitted = False
            password1 = ''
            password2 = ''
            break
        else:
            if event in ("Submit", "-newpassword2-_Enter"):
                submitted = True
                # print('Clicked Submit')
                currPassword = values['-currentPassword-']
                password1 = values['-newpassword1-']
                password2 = values['-newpassword2-']
                if (currPassword == currentPassword) and (password1 == password2) and (currPassword != password1) and (
                        len(password1) >= 6):
                    try:
                        updatePassword(db_name=db_name, username=currentUser, password=password1)
                        progressBar(f"Changing password for {currentUser}", theme="DarkBlue16")
                        # insertAuditRecord(db_name=db_name, action=CHANGED_OWN_PASSWORD, user=currentUser, role=currentRole,
                        #                   remarks=f"Successfully changed own password")
                    except:
                        pass
                    break
                elif len(password1) < 6:
                    submitted = False
                    password1 = ''
                    password2 = ''
                    showErrorMessage("Minimum length of password should be 6 characters. Enter data again.")
                    sg.theme('LightBlue2')
                elif (currPassword != currentPassword):
                    submitted = False
                    password1 = ''
                    password2 = ''
                    showErrorMessage("Current password does not match. Enter data again.")
                    sg.theme('LightBlue2')
                elif password1 != password2:
                    submitted = False
                    password1 = ''
                    password2 = ''
                    showErrorMessage("The 2 newwidgets passwords do not match. Enter data again.")
                    sg.theme('LightBlue2')
                elif (currPassword == password1):
                    submitted = False
                    password1 = ''
                    password2 = ''
                    showErrorMessage("The new password should not be same as previous password. Enter data again.")
                    sg.theme('LightBlue2')
    window.close()
    aWindowIsInProgress = False
    return submitted, currentUser, password1


def changePassword(currentUser: str, currentRole: str = "Supervisor", modal: bool = True):
    global aWindowIsInProgress
    if aWindowIsInProgress:
        # flashSimpleMessage("A menu operation is already in progress", auto_close_duration=2)
        return False, None, None

    db_name = getDatabaseName()
    userData = getIdAndUsernamesAndPasswordsAndRolesForActiveUsers(db_name)

    aWindowIsInProgress = True
    chosenUser = None
    validUsernames = []
    validOperatorUsernames = []
    for aRecord in userData:
        if (aRecord[1] != "superuser") and (aRecord[1] != currentUser):
            validUsernames.append(aRecord[1])
            if aRecord[3] == "Operator":
                validOperatorUsernames.append(aRecord[1])
    # if username not in validUsernames:
    #     showErrorMessage(f"No user in database with username {username}")
    #     return False, None, None
    # currentPassword = None
    # if username is not None:
    #     for aRecord in userData:
    #         if aRecord[1] == username:
    #             currentPassword = aRecord[2]
    #             break
    if len(validUsernames) == 0:
        showErrorMessage(f"No users available in database for changing password", auto_close_duration=2)
        aWindowIsInProgress = False
        return False, None, None
    password1: str = ''
    password2: str = ''
    submitted: bool = False
    sg.theme('LightBlue2')
    if currentRole == "Administrator":
        layout = [
            [sg.Text("Username", size=(20, 1), font=16),
             sg.Combo(values=validUsernames, default_value=validUsernames[0] if len(validUsernames) > 0 else '',
                      font=16, k='-username-')],
            [sg.Text("Enter New Password", size=(20, 1), font=16),
             sg.InputText(key='-newpassword1-', font=16, password_char='*')],
            [sg.Text("Re-enter New Password", size=(20, 1), font=16),
             sg.InputText(key='-newpassword2-', font=16, password_char='*')],
            [sg.Button("Submit"), sg.Button("Cancel")]
        ]
    elif currentRole == "Manager" or currentRole == "Supervisor":
        if len(validOperatorUsernames) == 0:
            showErrorMessage(f"No operators available in database for changing password", auto_close_duration=2)
            aWindowIsInProgress = False
            return False, None, None
        layout = [
            [sg.Text("Username", size=(20, 1), font=16),
             sg.Combo(values=validOperatorUsernames,
                      default_value=validOperatorUsernames[0] if len(validOperatorUsernames) > 0 else '', font=16,
                      k='-username-')],
            [sg.Text("Enter New Password", size=(20, 1), font=16),
             sg.InputText(key='-newpassword1-', font=16, password_char='*')],
            [sg.Text("Re-enter New Password", size=(20, 1), font=16),
             sg.InputText(key='-newpassword2-', font=16, password_char='*')],
            [sg.Button("Submit"), sg.Button("Cancel")]
        ]
    else:
        showErrorMessage(f"Unknown Role : {currentRole}", auto_close_duration=2)
        aWindowIsInProgress = False
        return False, None, None

    # else:
    #     layout = [
    #                 [sg.Text("Current Password", size=(20, 1), font=16), sg.InputText(key='-currentPassword-', font=16, password_char='*')],
    #                 [sg.Text("Enter New Password", size=(20, 1), font=16), sg.InputText(key='-newpassword1-', font=16, password_char='*')],
    #                 [sg.Text("Re-enter New Password", size=(20, 1), font=16), sg.InputText(key='-newpassword2-', font=16, password_char='*')],
    #                 [sg.Button("Submit"), sg.Button("Cancel")]
    #             ]

    window = sg.Window(f"Change Password for users : ", layout, modal=True, keep_on_top=True, finalize=True,
                       disable_minimize=True, grab_anywhere=False, disable_close=True)
    window['-username-'].set_focus()
    window['-newpassword2-'].bind("<Return>", "_Enter")

    while True:
        event, values = window.read()
        if event == 'Cancel' or event == sg.WIN_CLOSED:
            password1 = ''
            password2 = ''
            submitted = False
            break
        else:
            if event in ("Submit", "-newpassword2-_Enter"):
                submitted = True
                # print('Clicked Submit')
                # if currentRole == "Operator":
                #     currPassword = values['-currentPassword-']
                #     password1 = values['-newpassword1-']
                #     password2 = values['-newpassword2-']
                #     if (currPassword == currentPassword) and (password1 == password2):
                #         updatePassword(username=username, password=password1)
                #         progressBar(f"Changing password for {username}", theme="DarkBlue16")
                #         break
                #     elif (currPassword != currentPassword):
                #         showErrorMessage("Current password does not match. Enter data again.")
                #     elif password1 != password2:
                #         showErrorMessage("The 2 newwidgets passwords do not match. Enter data again.")
                # else:
                chosenUser = values['-username-']
                password1 = values['-newpassword1-']
                password2 = values['-newpassword2-']
                if (password1 != password2):
                    password1 = ''
                    password2 = ''
                    submitted = False
                    showErrorMessage("The 2 newwidgets passwords do not match. Enter data again.")
                    sg.theme('LightBlue2')
                elif len(password1) < 6:
                    password1 = ''
                    password2 = ''
                    submitted = False
                    showErrorMessage("Minimum length of password should be 6 characters. Enter data again.")
                    sg.theme('LightBlue2')
                else:
                    try:
                        updatePassword(db_name=db_name, username=chosenUser, password=password1)
                        progressBar(f"Changing password for {chosenUser}", theme="DarkBlue16")
                        # insertAuditRecord(db_name=db_name, action=CHANGED_OTHERS_PASSWORD, user=currentUser, role=currentRole,
                        #                   remarks=f"Successfully changed password for {chosenUser}")
                    except:
                        pass
                    break
    window.close()
    aWindowIsInProgress = False
    return submitted, chosenUser, password1


def inactivateUser(currentUser: str, currentRole: str = "Supervisor", modal: bool = True):
    global aWindowIsInProgress
    if aWindowIsInProgress:
        # flashSimpleMessage("A menu operation is already in progress", auto_close_duration=2)
        return False, None

    db_name = getDatabaseName()
    userData = getIdAndUsernamesAndPasswordsAndRolesForActiveUsers(db_name)

    aWindowIsInProgress = True
    validUsernames = []
    validOperatorUsernames = []
    for aRecord in userData:
        if aRecord[1].lower() != "superuser":
            validUsernames.append(aRecord[1])
            if aRecord[3].lower() == "operator":
                validOperatorUsernames.append(aRecord[1])

    if len(validUsernames) == 0:
        showErrorMessage("No users registered in database")
        aWindowIsInProgress = False
        return False, None
    submitted = False
    username = None
    sg.theme('DarkRed1')
    if currentRole.lower() == "administrator":
        layout = [
            [sg.Text("Username : ", size=(20, 1), font=16),
             sg.Combo(values=validUsernames, default_value=validUsernames[0] if len(validUsernames) > 0 else '',
                      font=16, k='-username-')],
            [sg.Button("Submit"), sg.Button("Cancel")]
        ]
    elif currentRole.lower() == "manager" or currentRole.lower() == "supervisor":
        if len(validOperatorUsernames) == 0:
            showErrorMessage("No users registered in database")
            aWindowIsInProgress = False
            return False, None
        layout = [
            [sg.Text("Username : ", size=(20, 1), font=16),
             sg.Combo(values=validOperatorUsernames,
                      default_value=validOperatorUsernames[0] if len(validOperatorUsernames) > 0 else '', font=16,
                      k='-username-')],
            [sg.Button("Submit"), sg.Button("Cancel")]
        ]
    else:
        showErrorMessage(f"Unknown Role : {currentRole}")
        aWindowIsInProgress = False
        return False, None

    window = sg.Window(f"Inactivate User", layout, return_keyboard_events=True, modal=True, keep_on_top=True,
                       finalize=True, disable_minimize=True, grab_anywhere=False, disable_close=True)
    window['-username-'].set_focus()
    window['-username-'].bind("<Return>", "_Enter")

    while True:
        event, values = window.read()
        if event == 'Cancel' or event == sg.WIN_CLOSED:
            username = None
            submitted = False
            break
        else:
            if event in ("Submit", "-username-_Enter"):
                submitted = True
                # print('Clicked Submit')
                username = values['-username-']
                confirmationStatement = f"Inactivate user {username}. Are you sure ?"
                confirmed: str = getConfirmation(confirmationStatement)
                if (confirmed.upper() == 'OK'):
                    try:
                        inactivateUserInDatabase(db_name=db_name, username=username)
                        # insertAuditRecord(db_name=db_name, action=INACTIVATED_USER, user=currentUser, role=currentRole,
                        #                   remarks=f"Successfully inactivated user {username}")
                        progressBar(f"Inactivating user {username}", theme="LightBrown6")
                    except:
                        pass
                    break
                else:
                    showErrorMessage(f"Leaving {username} activated", auto_close_duration=2)
                    sg.theme('DarkRed1')
                    username = None
                    submitted = False
    window.close()
    aWindowIsInProgress = False
    return submitted, username


def activateUser(currentUser: str, currentRole: str, modal: bool = True):
    global aWindowIsInProgress
    if aWindowIsInProgress:
        # flashSimpleMessage("A menu operation is already in progress", auto_close_duration=2)
        return False, None

    db_name = getDatabaseName()
    userData = getIdAndUsernamesAndPasswordsForInactiveUsers(db_name=db_name)

    aWindowIsInProgress = True
    validUsernames = []
    for aRecord in userData:
        validUsernames.append(aRecord[1])
    if len(validUsernames) == 0:
        showErrorMessage(f"Currently there are no inactive users", auto_close_duration=2)
        aWindowIsInProgress = False
        return False, None
    submitted = False
    username = None
    sg.theme('DarkGreen4')
    layout = [
        [sg.Text("Username : ", size=(20, 1), font=16),
         sg.Combo(values=validUsernames, default_value=validUsernames[0] if len(validUsernames) > 0 else '', font=16,
                  k='-username-')],
        [sg.Button("Submit"), sg.Button("Cancel")]
    ]
    window = sg.Window(f"Activate User", layout, return_keyboard_events=True, modal=True, keep_on_top=True,
                       finalize=True, disable_minimize=True, grab_anywhere=False, disable_close=True)
    window['-username-'].set_focus()
    window['-username-'].bind("<Return>", "_Enter")

    while True:
        event, values = window.read()
        if event == 'Cancel' or event == sg.WIN_CLOSED:
            username = None
            submitted = False
            break
        else:
            if event in ("Submit", "-username-_Enter"):
                submitted = True
                # print('Clicked Submit')
                username = values['-username-']
                confirmationStatement = f"Activate user {username}. Are you sure ?"
                confirmed: str = getConfirmation(confirmationStatement)
                if (confirmed.upper() == 'OK'):
                    try:
                        activateInactiveUserInDatabase(db_name=db_name, username=username)
                        # insertAuditRecord(db_name=db_name, action=ACTIVATED_USER, user=currentUser, role=currentRole,
                        #                   remarks=f"Successfully re-activated user {username}")
                        progressBar(f"Activating user {username}", theme="LightBlue6")
                    except:
                        submitted = True
                        username = None
                        pass
                    break
                else:
                    showErrorMessage(f"Leaving {username} inactivated", auto_close_duration=2)
                    sg.theme('DarkGreen4')
                    submitted = False
                    username = None
    window.close()
    aWindowIsInProgress = False
    return submitted, username


# ****************************************** End - User Management Methods ****************************************

# ****************************************** Begin - Mode Management Method ****************************************

def chooseMode(modal: bool = True):
    global aWindowIsInProgress
    if aWindowIsInProgress:
        return "TEST"

    sg.theme('DarkTeal9')
    modes = ['Test', 'Production']
    submitted = False
    mode = modes[0]
    layout = [
        [sg.Text("Run system in Mode (Cancel to exit application):", size=(40, 1), font=16),
         sg.Combo(values=modes, default_value=modes[0], font=16, k='-mode-')],
        [sg.Button("Submit"), sg.Button("Cancel")]
    ]

    aWindowIsInProgress = True
    window = sg.Window(f"Choose Mode as Test or Production. Cancel will close the application.", layout,
                       return_keyboard_events=True, modal=True, keep_on_top=True, finalize=True, disable_minimize=True,
                       grab_anywhere=False, disable_close=True)
    window['-mode-'].set_focus()
    window['-mode-'].bind("<Return>", "_Enter")

    while True:
        event, values = window.read()
        if event == 'Cancel' or event == sg.WIN_CLOSED:
            submitted = False
            break
        else:
            if event in ("Submit", "-mode-_Enter"):
                submitted = True
                mode = values['-mode-']
                confirmationStatement = f"Run system in mode = {mode}"
                confirmed: str = getConfirmation(confirmationStatement)
                if (confirmed.upper() == 'OK'):
                    progressBar(f"Initialising system in mode = {mode}...", theme="DarkBlue16")
                    break
                else:
                    showErrorMessage(f"Please choose a mode", auto_close_duration=2)
                    sg.theme('DarkTeal9')
    window.close()
    aWindowIsInProgress = False
    if submitted:
        flashSimpleMessage(f"Currently chosen mode is {mode.upper()}")
    return submitted, mode


# ****************************************** End - Mode Management Method ****************************************

# ****************************************** Begin - Role Management Methods ****************************************

def changeRole(currentUser: str, currentRole: str = "Supervisor", modal: bool = True):
    global aWindowIsInProgress
    if aWindowIsInProgress:
        # flashSimpleMessage("A menu operation is already in progress", auto_close_duration=2)
        return False, None, None

    db_name = getDatabaseName()
    userData = getIdAndUsernamesAndPasswordsAndRolesForActiveUsers(db_name)

    aWindowIsInProgress = True
    validUsernames = []
    validOperatorUsernames = []
    for aRecord in userData:
        if aRecord[1] != "superuser":
            validUsernames.append(aRecord[1])
            if aRecord[3] == "Operator":
                validOperatorUsernames.append(aRecord[1])
    if len(validUsernames) == 0:
        showErrorMessage(f"No users available in database for changing role", auto_close_duration=2)
        aWindowIsInProgress = False
        return False, None, None
    submitted = False
    username: str | None = None
    role: str | None = None
    sg.theme('LightBlue2')
    if currentRole == "Administrator":
        layout = [
            [sg.Text("Username : ", size=(20, 1), font=16),
             sg.Combo(values=validUsernames, default_value=validUsernames[0] if len(validUsernames) > 0 else '',
                      font=16, k='-username-')],
            [sg.Text("Change Role to :", size=(20, 1), font=16),
             sg.Combo(values=allowed_roles, default_value=allowed_roles[0], font=16, k='-role-')],
            [sg.Button("Submit"), sg.Button("Cancel")]
        ]
    elif currentRole == "Manager" or currentRole == "Supervisor":
        if len(validOperatorUsernames) == 0:
            showErrorMessage(f"No operators available in database for changing role", auto_close_duration=2)
            aWindowIsInProgress = False
            return False, None, None
        layout = [
            [sg.Text("Username : ", size=(20, 1), font=16),
             sg.Combo(values=validOperatorUsernames,
                      default_value=validOperatorUsernames[0] if len(validOperatorUsernames) > 0 else '',
                      font=16, k='-username-')],
            [sg.Text("Change Role to :", size=(20, 1), font=16),
             sg.Combo(values=allowed_roles[1:], default_value=allowed_roles[1], font=16, k='-role-')],
            [sg.Button("Submit"), sg.Button("Cancel")]
        ]
    else:
        showErrorMessage(f"Unknown Role : {currentRole}")
        aWindowIsInProgress = False
        return False, None, None

    window = sg.Window(f"Change Role", layout, return_keyboard_events=True, modal=True, keep_on_top=True, finalize=True,
                       disable_minimize=True, grab_anywhere=False, disable_close=True)
    window['-username-'].set_focus()
    window['-role-'].bind("<Return>", "_Enter")

    aWindowIsInProgress = True
    while True and aWindowIsInProgress:
        event, values = window.read()
        if event == 'Cancel' or event == sg.WIN_CLOSED:
            username = None
            role = None
            submitted = False
            break
        else:
            if event in ("Submit", "_role-_Enter"):
                submitted = True
                # print('Clicked Submit')
                username = values['-username-']
                role = values['-role-']
                confirmationStatement = f"Change role of user {username} to {role}"
                confirmed: str = getConfirmation(confirmationStatement)
                if (confirmed.upper() == 'OK'):
                    try:
                        updateRole(db_name=db_name, username=username, role_name=role)
                        progressBar(f"Changing role for {username}", theme="DarkBlue16")
                        # insertAuditRecord(db_name=db_name, action=CHANGED_USER_ROLE, user=currentUser, role=currentRole,
                        #                   remarks=f"Changed role of {username} to role {role}")
                    except:
                        username = None
                        role = None
                        pass
                    break
                else:
                    showErrorMessage(f"Role not changed for {username}", auto_close_duration=2)
                    sg.theme('LightBlue2')
                    username = None
                    role = None
    window.close()
    aWindowIsInProgress = False
    return submitted, username, role


# ****************************************** End - Role Management Methods ****************************************

# ****************************************** Begin - Production Report Generation Methods *************************************

def createProductionReportByDateLimits():
    done = False

    global aWindowIsInProgress
    if aWindowIsInProgress:
        # flashSimpleMessage("A menu operation is already in progress", auto_close_duration=2)
        return done
    aWindowIsInProgress = True

    sg.theme('LightBlue3')
    db_name = getDatabaseName()
    layout = [
        [sg.Text('Production Report Needed From Date : ', size=(40, 1)), sg.InputText(key='-fromdate-'),
         sg.CalendarButton("Select Date", close_when_date_chosen=True, target="-fromdate-", format='%Y-%m-%d',
                           size=(10, 1))],
        [sg.Text('Production Report Needed To Date : ', size=(40, 1)), sg.InputText(key='-todate-'),
         sg.CalendarButton("Select Date", close_when_date_chosen=True, target="-todate-", format='%Y-%m-%d',
                           size=(10, 1))],
        [sg.Button("Submit"), sg.Button("Clear"), sg.Button("Exit")]
    ]

    window = sg.Window(f' Generate production report for a period', layout, modal=True, keep_on_top=True, finalize=True,
                       disable_minimize=True, grab_anywhere=False, disable_close=False)
    window['-fromdate-'].set_focus()

    def clear_input(window):
        for key, element in window.key_dict.items():
            if isinstance(element, sg.Input):
                element.update(value='')

    while True and aWindowIsInProgress:
        event, values = window.read()
        if (event == "Exit") or (event == sg.WIN_CLOSED):
            showErrorMessage("Cancelling.\nNo report generated.", auto_close_duration=1)
            break
        if event == 'Clear':
            clear_input(window)
        if event == 'Submit':
            fromDate = values['-fromdate-']
            toDate = values['-todate-']
            fromPythonDate = datetime.strptime(fromDate, "%Y-%m-%d")
            toPythonDate = datetime.strptime(toDate, "%Y-%m-%d")
            # addDays = relativedelta(days=1)
            addDays = timedelta(days=1)
            toPythonDate = toPythonDate + addDays
            # if toPythonDate <= fromPythonDate:
            if toPythonDate < fromPythonDate:
                showErrorMessage("'To Date' cannot be less than 'From Date'", auto_close_duration=2)
                sg.theme('LightBlue3')
            else:
                toDate1 = datetime.strftime(toPythonDate, "%Y-%m-%d")
                confirmationStatement = f"Generate summary report for period (both days inclusive):\nStartingDate : {fromDate}\nEnd date : {toDate}"
                confirmed: str = getConfirmation(confirmationStatement)
                if (confirmed.upper() == 'OK'):
                    try:
                        csv_data = getDataByDateLimits(startDate=fromDate, endDate=toDate1, db_name=db_name)
                        try:
                            fName = writeReportToFile(csv_data=csv_data,
                                                      reportType="ProductionReportAllModelsByDateLimits")
                            done = True
                            showMessage(f"Report saved to {fName}")
                            # insertAuditRecord(db_name=db_name, action=SAVED_FROM_TO_REPORT, user=currentUser,
                            #                   role=currentRole,
                            #                   remarks=f"Production report from {fromDate} to {toDate} for medicine {med_name} for customer {cust_name}")
                        except:
                            showErrorMessage("Report generation failed.\n", auto_close_duration=1)
                    except:
                        showErrorMessage("Report generation failed.\n", auto_close_duration=1)
                    break
                else:
                    showErrorMessage("Cancelling.\nPlease choose dates again.", auto_close_duration=1)
    aWindowIsInProgress = False
    # printLight(resultKeyString)
    window.close()
    return done


def createProductionReportByModelNameAndDateLimits():
    done = False

    global aWindowIsInProgress
    if aWindowIsInProgress:
        # flashSimpleMessage("A menu operation is already in progress", auto_close_duration=2)
        return done
    aWindowIsInProgress = True

    sg.theme('LightBlue3')
    db_name = getDatabaseName()
    models = getUniqueModelNames(db_name=db_name)
    layout = [
        [sg.Text("Choose Model for which you want to generate report : ", size=(55, 1), font=16),
         sg.Combo(values=models,
                  default_value=models[0] if len(models) > 0 else '',
                  font=16, k='-modelname-')],
        [sg.Text('From Date : ', size=(15, 1)), sg.InputText(key='-fromdate-'),
         sg.CalendarButton("Select Date", close_when_date_chosen=True, target="-fromdate-", format='%Y-%m-%d',
                           size=(10, 1))],
        [sg.Text('To Date : ', size=(15, 1)), sg.InputText(key='-todate-'),
         sg.CalendarButton("Select Date", close_when_date_chosen=True, target="-todate-", format='%Y-%m-%d',
                           size=(10, 1))],
        [sg.Button("Submit"), sg.Button("Clear"), sg.Button("Exit")]
    ]

    window = sg.Window(f' Generate production report for a model for a period', layout, modal=True, keep_on_top=True,
                       finalize=True, disable_minimize=True, grab_anywhere=False, disable_close=False)
    try:
        window['-modelname-'].set_focus()
    except:
        window.bring_to_front()

    def clear_input(window):
        for key, element in window.key_dict.items():
            if isinstance(element, sg.Input):
                element.update(value='')

    while True and aWindowIsInProgress:
        event, values = window.read()
        if (event == "Exit") or (event == sg.WIN_CLOSED):
            showErrorMessage("Cancelling.\nNo report generated.")
            break
        if event == 'Clear':
            clear_input(window)
        if event == 'Submit':
            modelName = values['-modelname-']
            fromDate = values['-fromdate-']
            toDate = values['-todate-']
            fromPythonDate = datetime.strptime(fromDate, "%Y-%m-%d")
            toPythonDate = datetime.strptime(toDate, "%Y-%m-%d")
            # addDays = relativedelta(days=1)
            addDays = timedelta(days=1)
            toPythonDate = toPythonDate + addDays
            # if toPythonDate <= fromPythonDate:
            if toPythonDate < fromPythonDate:
                showErrorMessage("'To Date' cannot be less than 'From Date'")
                sg.theme('LightBlue3')
            else:
                toDate1 = datetime.strftime(toPythonDate, "%Y-%m-%d")
                confirmationStatement = f"Generate report for model {modelName} for period (both days inclusive):\nStartingDate : {fromDate}\nEnd date : {toDate}"
                confirmed: str = getConfirmation(confirmationStatement)
                if (confirmed.upper() == 'OK'):
                    try:
                        csv_data = getDataByModelNameAndDateLimits(modelName=modelName, startDate=fromDate,
                                                                   endDate=toDate1, db_name=db_name)
                        try:
                            fName = writeReportToFile(csv_data=csv_data,
                                                      reportType="ProductionReportByModelNameAndDateLimits")
                            done = True
                            showMessage(f"Report saved to {fName}")
                            # insertAuditRecord(db_name=db_name, action=SAVED_FROM_TO_REPORT, user=currentUser,
                            #                   role=currentRole,
                            #                   remarks=f"Production report from {fromDate} to {toDate} for medicine {med_name} for customer {cust_name}")
                        except:
                            showErrorMessage("Report generation failed.\n", auto_close_duration=1)
                    except:
                        showErrorMessage("Report generation failed.\n", auto_close_duration=1)
                    break
                else:
                    showErrorMessage("Cancelling.\nPlease choose dates again.", auto_close_duration=1)
    aWindowIsInProgress = False
    # printLight(resultKeyString)
    window.close()
    return done


def createProductionReportByModelName():
    done = False

    global aWindowIsInProgress
    if aWindowIsInProgress:
        # flashSimpleMessage("A menu operation is already in progress", auto_close_duration=2)
        return done
    aWindowIsInProgress = True

    sg.theme('LightBlue3')
    db_name = getDatabaseName()
    models = getUniqueModelNames(db_name=db_name)
    layout = [
        [sg.Text("Choose Model for which you want to generate report : ", size=(55, 1), font=16),
         sg.Combo(values=models,
                  default_value=models[0] if len(models) > 0 else '',
                  font=16, k='-modelname-')],
        [sg.Button("Submit"), sg.Button("Clear"), sg.Button("Exit")]
    ]

    window = sg.Window(f' Generate production report for a model', layout, modal=True, keep_on_top=True, finalize=True,
                       disable_minimize=True, grab_anywhere=False, disable_close=False)
    try:
        window['-modelname-'].set_focus()
        window['-modelname-'].bind("<Return>", "_Enter")
    except:
        window.bring_to_front()

    def clear_input(window):
        for key, element in window.key_dict.items():
            if isinstance(element, sg.Input):
                element.update(value='')

    while True and aWindowIsInProgress:
        event, values = window.read()
        if (event == "Exit") or (event == sg.WIN_CLOSED):
            # printBoldYellow(f"Got Window Close event in createProductionReportByModelName()")
            showErrorMessage("Cancelling.\nNo report generated.", auto_close_duration=1)
            break
        if event == 'Clear':
            clear_input(window)
        if event == 'Submit':
            modelName = values['-modelname-']
            confirmationStatement = f"Generate report for model {modelName}"
            confirmed: str = getConfirmation(confirmationStatement)
            if (confirmed.upper() == 'OK'):
                try:
                    csv_data = getDataByModelName(modelName=modelName, db_name=db_name)
                    try:
                        fName = writeReportToFile(csv_data=csv_data, reportType="AllTimeProductionReportByModelName")
                        done = True
                        showMessage(f"Report saved to {fName}")
                        # insertAuditRecord(db_name=db_name, action=SAVED_FROM_TO_REPORT, user=currentUser,
                        #                   role=currentRole,
                        #                   remarks=f"Production report from {fromDate} to {toDate} for medicine {med_name} for customer {cust_name}")
                    except:
                        showErrorMessage("Report generation failed.\n", auto_close_duration=1)
                except:
                    showErrorMessage("Report generation failed.\n", auto_close_duration=1)

                break
            else:
                showErrorMessage("Cancelling.\nPlease choose dates again.", auto_close_duration=1)
    aWindowIsInProgress = False
    # printLight(resultKeyString)
    window.close()
    return done


def createProductionReportOfTodayByModelName():
    done = False

    global aWindowIsInProgress
    if aWindowIsInProgress:
        # flashSimpleMessage("A menu operation is already in progress", auto_close_duration=2)
        return done
    aWindowIsInProgress = True

    sg.theme('LightBlue3')
    db_name = getDatabaseName()
    models = getUniqueModelNames(db_name=db_name)
    layout = [
        [sg.Text("Choose Model for which you want to generate today's report : ", size=(55, 1), font=16),
         sg.Combo(values=models,
                  default_value=models[0] if len(models) > 0 else '',
                  font=16, k='-modelname-')],
        [sg.Button("Submit"), sg.Button("Clear"), sg.Button("Exit")]
    ]

    window = sg.Window(f" Generate today's production report for a model", layout, modal=True, keep_on_top=True,
                       finalize=True, disable_minimize=True, grab_anywhere=False, disable_close=False)
    try:
        window['-modelname-'].set_focus()
        window['-modelname-'].bind("<Return>", "_Enter")
    except:
        window.bring_to_front()

    def clear_input(window):
        for key, element in window.key_dict.items():
            if isinstance(element, sg.Input):
                element.update(value='')

    while True and aWindowIsInProgress:
        event, values = window.read()
        if (event == "Exit") or (event == sg.WIN_CLOSED):
            showErrorMessage("Cancelling.\nNo report generated.", auto_close_duration=1)
            break
        if event == 'Clear':
            clear_input(window)
        if event == 'Submit':
            modelName = values['-modelname-']
            confirmationStatement = f"Generate today's report for model {modelName}"
            confirmed: str = getConfirmation(confirmationStatement)
            if (confirmed.upper() == 'OK'):
                try:
                    csv_data = getDataOfTodayByModelNumber(modelName=modelName, db_name=db_name)
                    try:
                        fName = writeReportToFile(csv_data=csv_data, reportType="DayProductionReportByModelName")
                        done = True
                        showMessage(f"Report saved to {fName}")
                        # insertAuditRecord(db_name=db_name, action=SAVED_FROM_TO_REPORT, user=currentUser,
                        #                   role=currentRole,
                        #                   remarks=f"Production report from {fromDate} to {toDate} for medicine {med_name} for customer {cust_name}")
                    except:
                        showErrorMessage("Report generation failed.\n", auto_close_duration=1)
                except:
                    showErrorMessage("Report generation failed.\n", auto_close_duration=1)
                break
            else:
                showErrorMessage("Cancelling.\nPlease choose dates again.", auto_close_duration=1)
    aWindowIsInProgress = False
    # printLight(resultKeyString)
    window.close()
    return done


def createProductionReportOfToday():
    done = False

    global aWindowIsInProgress
    if aWindowIsInProgress:
        # flashSimpleMessage("A menu operation is already in progress", auto_close_duration=2)
        return done
    aWindowIsInProgress = True

    sg.theme('LightBlue3')
    db_name = getDatabaseName()
    layout = [
        [sg.Text("Generate today's full production report ", size=(55, 1), font=16), ],
        [sg.Button("Submit"), sg.Button("Clear"), sg.Button("Exit")]
    ]

    window = sg.Window(f" Generate today's production report for ALL models", layout, modal=True, keep_on_top=True,
                       finalize=True, disable_minimize=True, grab_anywhere=False, disable_close=False)

    def clear_input(window):
        for key, element in window.key_dict.items():
            if isinstance(element, sg.Input):
                element.update(value='')

    while True and aWindowIsInProgress:
        event, values = window.read()
        if (event == "Exit") or (event == sg.WIN_CLOSED):
            showErrorMessage("Cancelling.\nNo report generated.", auto_close_duration=1)
            break
        if event == 'Clear':
            clear_input(window)
        if event == 'Submit':
            confirmationStatement = f"Generate today's report for all models ?"
            confirmed: str = getConfirmation(confirmationStatement)
            if (confirmed.upper() == 'OK'):
                try:
                    csv_data = getAllDataOfToday(db_name=db_name)
                    try:
                        fName = writeReportToFile(csv_data=csv_data, reportType="DayProductionReport")
                        done = True
                        showMessage(f"Report saved to {fName}")
                        # insertAuditRecord(db_name=db_name, action=SAVED_FROM_TO_REPORT, user=currentUser,
                        #                   role=currentRole,
                        #                   remarks=f"Production report from {fromDate} to {toDate} for medicine {med_name} for customer {cust_name}")
                    except:
                        showErrorMessage("Report generation failed.\n", auto_close_duration=1)
                except:
                    showErrorMessage("Report generation failed.\n", auto_close_duration=1)
                break
            else:
                showErrorMessage("Cancelling.\nPlease choose dates again.", auto_close_duration=1)
    aWindowIsInProgress = False
    # printLight(resultKeyString)
    window.close()
    return done


def writeReportToFile(csv_data: str, reportType: str):
    if csv_data is None:
        return
    if reportType is None:
        return
    baseDir = CosThetaConfigurator.getInstance().getBaseDirForReports()
    relativeDirectory = f"{getCurrentMode()}/{reportType}/"
    baseFileName = f"Production_Report_{getTodaysDateAsString()}"
    fullFileName = f"{baseDir}{relativeDirectory}{baseFileName}_{getCurrentTime()}.csv"
    os.makedirs(os.path.dirname(fullFileName), exist_ok=True)
    with open(fullFileName, 'w', newline='') as file:
        file.write(csv_data)
    return fullFileName


# ****************************************** End - Production Report Generation Methods *************************************


# ****************************************** Start - Machine Settings Methods *************************************

def updateMachineSettingsDialog():
    """
    Display a dialog to update machine settings (PLC parameters).
    Validates input and inserts a new record in the database (audit trail).

    Returns:
        bool: True if settings were updated successfully, False otherwise
    """
    done = False

    global aWindowIsInProgress
    if aWindowIsInProgress:
        return done
    aWindowIsInProgress = True

    sg.theme('LightBlue3')
    db_name = getDatabaseName()

    # Get current settings from database (latest record)
    current_settings = getMachineSettings(db_name)

    # Default values if no settings exist
    default_values = {
        'NoOfRotation1CCW': current_settings.get('NoOfRotation1CCW', 1),
        'NoOfRotation1CW': current_settings.get('NoOfRotation1CW', 1),
        'NoOfRotation2CCW': current_settings.get('NoOfRotation2CCW', 1),
        'NoOfRotation2CW': current_settings.get('NoOfRotation2CW', 1),
        'RotationUnitRPM': current_settings.get('RotationUnitRPM', 60),
    }

    # Layout with input fields for each parameter
    layout = [
        [sg.Text("Update Machine Settings (PLC Parameters)", font=("Helvetica", 14, "bold"), justification="center")],
        [sg.HorizontalSeparator()],
        [sg.Text("")],
        [sg.Text("No. of Rotations 1 CCW (0-10):", size=(28, 1), font=12),
         sg.Input(default_text=str(default_values['NoOfRotation1CCW']), key='-ROT1CCW-', size=(10, 1), font=12)],
        [sg.Text("No. of Rotations 1 CW (0-10):", size=(28, 1), font=12),
         sg.Input(default_text=str(default_values['NoOfRotation1CW']), key='-ROT1CW-', size=(10, 1), font=12)],
        [sg.Text("No. of Rotations 2 CCW (0-10):", size=(28, 1), font=12),
         sg.Input(default_text=str(default_values['NoOfRotation2CCW']), key='-ROT2CCW-', size=(10, 1), font=12)],
        [sg.Text("No. of Rotations 2 CW (0-10):", size=(28, 1), font=12),
         sg.Input(default_text=str(default_values['NoOfRotation2CW']), key='-ROT2CW-', size=(10, 1), font=12)],
        [sg.Text("Rotation Speed RPM (1-120):", size=(28, 1), font=12),
         sg.Input(default_text=str(default_values['RotationUnitRPM']), key='-RPM-', size=(10, 1), font=12)],
        [sg.Text("")],
        [sg.HorizontalSeparator()],
        [sg.Text("")],
        [sg.Button("Update", size=(12, 1), font=12),
         sg.Button("Reset", size=(12, 1), font=12),
         sg.Button("Cancel", size=(12, 1), font=12)]
    ]

    window = sg.Window(
        " Update Machine Settings",
        layout,
        modal=True,
        keep_on_top=True,
        finalize=True,
        disable_minimize=True,
        grab_anywhere=False,
        disable_close=False,
        element_justification='center'
    )

    try:
        window['-ROT1CCW-'].set_focus()
    except:
        window.bring_to_front()

    def validate_rotation(value_str, field_name):
        """Validate rotation value (0-10)"""
        try:
            val = int(value_str.strip())
            if val < 0 or val > 10:
                return False, f"{field_name} must be between 0 and 10"
            return True, val
        except ValueError:
            return False, f"{field_name} must be a valid integer"

    def validate_rpm(value_str):
        """Validate RPM value (1-120)"""
        try:
            val = int(value_str.strip())
            if val < 1 or val > 200:
                return False, "RPM must be between 1 and 200"
            return True, val
        except ValueError:
            return False, "RPM must be a valid integer"

    def reset_fields(window, defaults):
        """Reset all fields to current database values"""
        window['-ROT1CCW-'].update(str(defaults['NoOfRotation1CCW']))
        window['-ROT1CW-'].update(str(defaults['NoOfRotation1CW']))
        window['-ROT2CCW-'].update(str(defaults['NoOfRotation2CCW']))
        window['-ROT2CW-'].update(str(defaults['NoOfRotation2CW']))
        window['-RPM-'].update(str(defaults['RotationUnitRPM']))

    while True and aWindowIsInProgress:
        event, values = window.read()

        if event in ("Cancel", sg.WIN_CLOSED):
            confirmed = getConfirmation(
                "Are you sure you want to cancel?",
                "Any unsaved changes will be lost."
            )
            if confirmed.upper() == 'OK':
                showErrorMessage("Operation cancelled.\nNo changes made.", auto_close_duration=2)
                break
            else:
                continue

        if event == 'Reset':
            reset_fields(window, default_values)
            continue

        if event == 'Update':
            # Validate all inputs
            errors = []
            validated_values = {}

            # Validate Rotation 1 CCW
            valid, result = validate_rotation(values['-ROT1CCW-'], "Rotation 1 CCW")
            if valid:
                validated_values['rot1ccw'] = result
            else:
                errors.append(result)

            # Validate Rotation 1 CW
            valid, result = validate_rotation(values['-ROT1CW-'], "Rotation 1 CW")
            if valid:
                validated_values['rot1cw'] = result
            else:
                errors.append(result)

            # Validate Rotation 2 CCW
            valid, result = validate_rotation(values['-ROT2CCW-'], "Rotation 2 CCW")
            if valid:
                validated_values['rot2ccw'] = result
            else:
                errors.append(result)

            # Validate Rotation 2 CW
            valid, result = validate_rotation(values['-ROT2CW-'], "Rotation 2 CW")
            if valid:
                validated_values['rot2cw'] = result
            else:
                errors.append(result)

            # Validate RPM
            valid, result = validate_rpm(values['-RPM-'])
            if valid:
                validated_values['rpm'] = result
            else:
                errors.append(result)

            # If there are validation errors, show them
            if errors:
                error_msg = "Validation Errors:\n\n" + "\n".join(f"• {e}" for e in errors)
                showErrorMessage(error_msg, auto_close_duration=5)
                continue

            # Show confirmation with the values to be saved
            confirm_msg = (
                f"Update Machine Settings with the following values?\n\n"
                f"Rotation 1 CCW: {validated_values['rot1ccw']}\n"
                f"Rotation 1 CW: {validated_values['rot1cw']}\n"
                f"Rotation 2 CCW: {validated_values['rot2ccw']}\n"
                f"Rotation 2 CW: {validated_values['rot2cw']}\n"
                f"Rotation RPM: {validated_values['rpm']}"
            )

            confirmed = getConfirmation(confirm_msg, "Click OK to save, Cancel to go back")

            if confirmed.upper() == 'OK':
                # Insert new record (for audit trail)
                try:
                    success = insertNewMachineSettings(
                        db_name=db_name,
                        no_of_rotation1_ccw=validated_values['rot1ccw'],
                        no_of_rotation1_cw=validated_values['rot1cw'],
                        no_of_rotation2_ccw=validated_values['rot2ccw'],
                        no_of_rotation2_cw=validated_values['rot2cw'],
                        rotation_unit_rpm=validated_values['rpm']
                    )

                    if success:
                        done = True
                        showMessage("Machine settings updated successfully!", auto_close_duration=3)
                        break
                    else:
                        showErrorMessage("Failed to update machine settings.\nPlease try again.", auto_close_duration=3)
                except Exception as e:
                    showErrorMessage(f"Error updating settings:\n{str(e)}", auto_close_duration=3)
            else:
                showErrorMessage("Update cancelled.\nPlease modify values and try again.", auto_close_duration=2)

    aWindowIsInProgress = False
    window.close()
    return done

# ****************************************** End - Machine Settings Methods *************************************


# submitted, successfullyInserted, nExistingRecordsWithSameUsername, username, firstname, middlename, lastname, password, email, mobile, role = createAccount()
# print(submitted, successfullyInserted, nExistingRecordsWithSameUsername, username, firstname, middlename, lastname, password, email, mobile, role)
# submitted, username, password = login()
# print(submitted, username, password)
# print(getJustPassword("Enter Password 1 "))
# print(getSimpleInput("Enter Batch No : "))
# ch = sg.popup_ok_cancel("Press Ok to proceed", "Press cancel to stop",  title="OkCancel")
# if ch=="OK":
#    print ("You pressed OK")
# if ch=="Cancel":
#    print ("You pressed Cancel")
# showErrorMessage("User already exists")
# print(getConfirmation("User : abcd\nEmail : sdf!ghj.com\nPassword : ghtrew \nRole : Administrator "))
# submitted, username, newpassword = changePassword("UB")
# print(login())
# print(createAccount())
# print(getIdAndUsernamesAndPasswordsAndRolesForActiveUsers())
# print(changePassword('UB'))
# print(getIdAndUsernamesAndPasswordsAndRolesForActiveUsers())
# print(changePassword('superuser', "Administrator"))
# print(getIdAndUsernamesAndPasswordsAndRolesForActiveUsers())
# print(changeRole())
# print(getIdAndUsernamesAndPasswordsAndRolesForActiveUsers())
# print(addBatchNumber())
# print(chooseBatchNumber())
# print(login())
# flashSimpleMessage(f"Sending the following report :\n\nBatch Number : 4365467567576\nStarting Date : 23 April, 2024 17:03:28\nEnding Date : 30 April, 2024 12:04:16\nOK : 2400 bottles\nNotOK : 360 bottles\n\n", auto_close_duration=10)
# print(sendBatchReport('1'))
# sendBatchReportFromDateToDate()
# displayScrollableColumnWithHeader("This is the \n3 line header\n=================",contentToBeDisplayed="ghgg lkjlk jl\ngkjkhlhlkhlkj;lj\ngkkjlikk;m,kk\nbvkgkjhjkh\n", size = (520, 540))
# reassignFoldersAndDatabaseForPersistence(mode="Test")
# sendAuditReportFromDateToDate("superuser", "Administrator", "date")
# sendDetailedReportByBatch("superuser", "Administrator", "239876543")
# showApplicationStartingScreen()
# showMessage(textToShow = "Type Input", auto_close_duration=6)
# flashSimpleMessage("A longish message that needs to wrap around and be seen by the people who are callling this", auto_close_duration=10)
# getJustPassword()