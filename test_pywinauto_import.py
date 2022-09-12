from pywinauto.application import Application
from pywinauto.findwindows import find_elements, find_window
#app = Application(backend='uia').start('C:\Program Files (x86)\Gilson\Trilution LH 4.0\core\LH.exe')
app = Application(backend='uia').connect(best_match='ApplicationCurrentUser')


#app.ApplicationCurrentUser.window(auto_id='picImport').setfocus()
#app.ApplicationCurrentUser.window(auto_id='picImport').click()
pic = app.top_window().window(auto_id='picImport')
print(dir(pic.wrapper_object()))

pic.set_focus()
pic.click_input()