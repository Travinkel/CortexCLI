
def prompt_for_self_explanation(prompt_text):
  """
  This function will prompt the user for a self-explanation and return their response.
  """
  print(prompt_text)
  response = input()
  return response

if __name__ == '__main__':
  prompt_for_self_explanation("Explain this to yourself.")
