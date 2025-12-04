
// When the revert button is clicked retrieve the previous value of the field.
// If a user changes the field, the revert button will return the field displayed
// when form was rendered
//function revertFields() {
//  $('.revert').on('click', function() {
//    var name = $(this).attr('name');
//    var val = $('#'+name).val();
//    var item_id = item_id;
//    console.log(item_id)
//    $.getJSON('/'+table_name+'/revert_changes', {
//      item_id: item_id,
//      field_name: name,
//      field_value: val,
//      field_type : $('#'+name).prop('tagName'),
//      multiple: $('#'+name).prop('multiple')
//    }, function(data) {
//        $('#'+name).val(data.value);
//        if ($('#'+name).prop('tagName') == 'SELECT'){
//            $('#'+name).selectpicker('refresh');
//            $('#'+name).selectpicker('render');
//        }
//
//    });
//    $('#'+name).next('.btn').after('<div>Hello</div>')
//    return false;
//  });
//};
