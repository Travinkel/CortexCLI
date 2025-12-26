# TODO: This is a mock UI for demonstration purposes.
# In a real-world scenario, this would be replaced with an interface
# to the actual CLI application's UI, allowing the test to drive
# and inspect the real application.

class StudyUI:
    def __init__(self, elements):
        self.elements = elements
        self.focused_element_index = -1

    def open(self):
        """Simulates opening the UI and focusing the first element."""
        print("UI is open.")
        if self.elements:
            self.focused_element_index = 0

    def get_focused_element(self):
        """Returns the currently focused element."""
        if 0 <= self.focused_element_index < len(self.elements):
            return self.elements[self.focused_element_index]
        return None

    def tab(self):
        """Simulates pressing the Tab key to navigate forward."""
        if self.elements:
            self.focused_element_index = (self.focused_element_index + 1) % len(self.elements)
            print(f"Tabbed to: {self.get_focused_element()}")

    def shift_tab(self):
        """Simulates pressing Shift+Tab to navigate backward."""
        if self.elements:
            self.focused_element_index = (self.focused_element_index - 1 + len(self.elements)) % len(self.elements)
            print(f"Shift-Tabbed to: {self.get_focused_element()}")

    def is_element_usable(self, element):
        """Checks if a given element is part of the UI and thus 'usable'."""
        return element in self.elements
