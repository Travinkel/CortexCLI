class CLI:
    def __init__(self):
        self.concept = None
        self.examples = []
        self.non_examples = []
        self.learner_discernment = False

    def set_concept(self, concept):
        self.concept = concept

    def present_example(self, example):
        self.examples.append(example)

    def present_non_example(self, non_example):
        self.non_examples.append(non_example)

    def has_learner_discerned_concept(self):
        if not self.examples or not self.non_examples:
            return False

        # Get the attributes of the first example
        attributes = self.examples[0].__dict__.keys()

        for attr in attributes:
            # Get the value of the attribute for the first example
            example_attr_value = getattr(self.examples[0], attr)

            # Check if this attribute value is invariant across all examples
            is_invariant_in_examples = all(
                hasattr(ex, attr) and getattr(ex, attr) == example_attr_value
                for ex in self.examples
            )

            if is_invariant_in_examples:
                # This is a candidate for a critical feature.
                # Now check if it's different for all non-examples.
                is_different_in_non_examples = all(
                    not hasattr(nex, attr) or getattr(nex, attr) != example_attr_value
                    for nex in self.non_examples
                )

                if is_different_in_non_examples:
                    # We found a critical feature that distinguishes examples from non-examples.
                    self.learner_discernment = True
                    return True

        # No single attribute was found to be the critical feature.
        self.learner_discernment = False
        return False
