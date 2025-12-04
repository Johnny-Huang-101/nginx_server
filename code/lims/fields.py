from datetime import datetime
from wtforms import DateField, FloatField

class NullableDateField(DateField):
    """
    Native WTForms DateField throws error for empty dates and using the
    Optional() validator does not allow any custom validation. This field
    inherits from the DateField and allows empy dates.

    """
    def process_formdata(self, valuelist):
        if valuelist:
            date_str = ' '.join(valuelist).strip()
            if date_str == '':
                self.data = None
                return
            try:
                self.data = datetime.strptime(date_str, self.format).date()
            except ValueError:
                self.data = None
                raise ValueError(self.gettext('Not a valid date value'))


class NullableFloatField(FloatField):
    """
    Native FloatField requires data by default, but the Optional validator can be used
    to override this behaviour. Unfortunately, the Optional validator cannot be used in combination
    with custom validators. Use this field to add custom validators to a float field.
    """
    def process_formdata(self, valuelist):
        if valuelist:
            if valuelist[0]:
                try:
                    self.data = float(valuelist[0])
                except ValueError:
                    self.data = None
                    raise ValueError(self.gettext('Not a valid float value'))
        else:
            self.data = None
