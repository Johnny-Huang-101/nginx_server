// Run disableCommentText and disableCommentID on load
$(document).ready(function () {
    disableCommentText();
    disableCommentId();
})

// Disable the comment_text field if a reference comment is selected
function disableCommentText() {
    var comment_id = $('#comment_id').val()
    console.log(comment_id)
    if (comment_id != 0) {
        $('#comment_text').attr('disabled', true);
    } else {
        $('#comment_text').attr('disabled', false);
    }
}
$('#comment_id').on('change', disableCommentText)

// Disable the comment_id field if a manual comment is entered
function disableCommentId() {
    var comment_text = $('#comment_text').val()
    console.log(comment_text)
    if (comment_text) {
        $('#comment_id').attr('disabled', true);
        $('#comment_id').selectpicker('refresh');
    } else {
        $('#comment_id').attr('disabled', false);
        $('#comment_id').selectpicker('refresh');
    }
}
$('#comment_text').on('keyup', disableCommentId)

// Populate the item_id dropdown based on the item_type selection
$('#comment_item_type').on('change', function() {
    var item_type = $(this).val();
    $.getJSON('/comment_instances/get_items/', {
      item_type: item_type,
    }, function(data) {
       var item_choices = '';
       for (var item of data.items) {
        item_choices += '<option value="' + item.id + '">' + item.name + '</option>';
       }
       var comment_choices = '';
       for (var comment of data.comments) {
        comment_choices += '<option value="' + comment.id + '">' + comment.name + '</option>';
       }

        $('#comment_item_id').html(item_choices);
        $('#comment_item_id').selectpicker('refresh');
        $('#comment_item_id').selectpicker('render');

        $('#comment_id').html(comment_choices);
        $('#comment_id').selectpicker('refresh');
        $('#comment_id').selectpicker('render');

    });
    return false;
});
