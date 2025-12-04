
$('#instrument_id').on('change', function() {
    var instrument_id = $('#instrument_id').val();
    $.getJSON('/assays/get_batch_templates/', {
              instrument_id: instrument_id,
            }, function(data) {
               var optionHTML = '';
               for (var item of data.batch_templates) {
                optionHTML += '<option value="' + item.id + '">' + item.name + '</option>';
            }
             $('#batch_template_id').html(optionHTML);
             $('#batch_template_id').selectpicker('refresh');
             $('#batch_template_id').selectpicker('render');
            });
            return false;
});
