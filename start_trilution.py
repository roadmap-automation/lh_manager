from pywinauto.application import Application
from pywinauto.findwindows import find_elements, find_window
#app = Application(backend='uia').start('C:\Program Files (x86)\Gilson\Trilution LH 4.0\core\LH.exe')

def click_button(btn):
    # helper routine for setting focus on a button and clicking it
    #btn.set_focus()
    if hasattr(btn.wrapper_object(), 'click'):
        # more robust because control does not have to be visible
        btn.click()
    else:
        # less robust because intervening mouse movements can mess it up
        btn.set_focus()
        btn.click_input()

def add_text(txtbox, text_to_add):
    # helper routine for adding text
    txtbox.set_text(text_to_add)

try:
    app = Application(backend='uia').connect(path='C:\Program Files (x86)\Gilson\Trilution LH 4.0\core\LH.exe')
except:
    app = Application(backend='uia').start('C:\Program Files (x86)\Gilson\Trilution LH 4.0\core\LH.exe')
    app.window(auto_id='Login').wait('enabled', timeout=20)
    click_button(app.window(auto_id='Login').window(auto_id='btnLogin'))

main_window = app.window(auto_id='LHApplications')
click_button(main_window.window(auto_id='btnRunList'))

application_window = app.window(auto_id='ApplicationRun')
picImport = application_window.window(auto_id='picImport')
click_button(picImport)

import_window = application_window.child_window(title='Import', control_type='Window')
add_text(import_window.child_window(auto_id='1148', control_type='Edit'), 'test2.tsl')
click_button(import_window.window(auto_id='1', control_type='Button'))
click_button(application_window.child_window(title='TRILUTION LH', control_type='Window').window(auto_id='btnOK'))
#loginwindow.print_control_identifiers()

#app.ApplicationCurrentUser.window(auto_id='picImport').setfocus()
#app.ApplicationCurrentUser.window(auto_id='picImport').click()
#pic = app.top_window().window(auto_id='picImport')
#print(dir(pic.wrapper_object()))

#pic.set_focus()
#pic.click_input()