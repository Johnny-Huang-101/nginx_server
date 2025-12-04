
from lims.models import Comments, module_definitions


def get_form_choices(form, comment_item_id=None, comment_item_type=None):
    """

    Get the choices for:
        - item_type
        - item_id

    Parameters
    ----------
    form (FlaskForm):
    item_id (int): None
        Set the value of item_id if item_id is not none.
    item_type:
        pre-filter item_id list on form render if item_type is not None.

    Returns
    -------
    form (FLaskForm)

    """
    # Get all of the item_types (modules)
    item_types = [(module, module) for module in module_definitions.keys()]
    form.comment_item_type.choices = item_types
    form.comment_item_type.choices.insert(0, (0, 'Please select an item type'))

    items = []

    if comment_item_type:
        # If item_type is not None, get the table and alias from
        # module definitions
        table = module_definitions[comment_item_type][0]
        alias = module_definitions[comment_item_type][2]
        # If an item_id is provided, set that option as the only choice and
        # disable the item_type and item_id fields. If item_id is None,
        # pull all items for that module displaying the alias.
        if comment_item_id:
            item = table.query.get(comment_item_id)
            items = [(item.id, getattr(item, alias))]
            # form.comment_item_type.data = comment_item_type
            form.comment_item_type.render_kw = {'disabled': True}
            # form.comment_item_id.data = comment_item_id
            form.comment_item_id.render_kw = {'disabled': True}
        else:
            items = [(item.id, getattr(item, alias)) for item in table.query.order_by(getattr(table, alias))]

        items.insert(0, (0, 'Please select an item'))

        # Get any global comments and comments for that module displaying
        # as code - comment_type - comment text e.g. 85 - Tests - Unidentified Peak Observed (F,B)
        comments = Comments.query.filter(Comments.comment_type.in_(['Global', comment_item_type]))
        comment_choices = [(comment.id, f"{comment.code} - {comment.comment_type} - {comment.comment}") for comment in
                           comments]
        comment_choices.insert(0, (0, '---'))

        form.comment_item_type.data = comment_item_type

        if comment_item_id:
            form.comment_item_id.data = comment_item_id
    else:
        items.insert(0, (0, 'No item type selected'))
        comment_choices = [(0, 'No item type selected')]

    form.comment_item_id.choices = items
    form.comment_id.choices = comment_choices

    return form


def process_form(form):
    """
    Although we are storing the id of the comment
    (if is not a manual comment, comment_id is None otherwise) and
    thus have access to the comment text for display through the relationship,
    we want to store the comment text at the time the comment was added. This also
    allows us to store manual comments.

    """
    kwargs = {}
    # Set the comment_type and comment_text values.
    comment = Comments.query.get(form.comment_id.data)
    if comment:
        kwargs['comment_type'] = comment.comment_type
        #kwargs['comment_text'] = comment.comment

    # If a manual comment is added, i.e., the comment_text field has values
    # set the comment_type to manual
    if form.comment_text.data:
        kwargs['comment_type'] = 'Manual'

    return kwargs