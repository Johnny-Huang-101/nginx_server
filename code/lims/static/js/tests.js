// Initialize the tests datatable
$(document).ready(function () {
    var table = $('#tests').DataTable({
        dom: 'tr',
        scrollCollapse: true,
        "aaSorting": [[ 0, "asc" ]],
        "language": {
        "emptyTable": "No tests assigned"
        },
        "pageLength": -1
    });
});


// Initialize the specimens datatable
$(document).ready(function () {
    let table = $('#specimens').DataTable({
        dom: 'tr',
        "aaSorting": [[ 1, "asc" ]],
        "language": {
         "emptyTable": "Please select a discipline to see available specimens"
         },
         "pageLength": -1
    });
});


// When the case_id is changed, clear the test and specimens tables
// and get the disciplines requested and performed. Update discipline selectfield.
$(function() {
      $('#case_id').on('change', function() {
        var case_id = document.getElementById("case_id").value;
         $('#specimens').DataTable().clear().draw();
         $('#tests').DataTable().clear().draw();
         $('#assay_id').attr('disabled', true);
         $('assay_id').selectpicker('val', "");
         $('#assay_id').selectpicker('refresh');
         $('#assay_id').selectpicker('render');
         $.getJSON('/tests/get_disciplines/', {
            case_id: case_id,
            }, function(data) {
                // set the disciplines as checked if requested/performed. If a discipline
                // is performed, disable the checkbox
                $('#toxicology').prop('checked', data.toxicology);
                $('#toxicology').attr('disabled', data.toxicology_requested)
                $('#biochemistry').prop('checked', data.biochemistry);
                $('#biochemistry').attr('disabled', data.biochemistry_requested)
                $('#histology').prop('checked', data.histology);
                $('#histology').attr('disabled', data.histology_requested)
                $('#external').prop('checked', data.external);
                $('#external').attr('disabled', data.external_requested)
                $('#toxicology_requested').prop('checked', data.toxicology_requested);
                $('#biochemistry_requested').prop('checked', data.biochemistry_requested);
                $('#histology_requested').prop('checked', data.histology_requested);
                $('#external_requested').prop('checked', data.external_requested);

               // Update specimen_id selectfield (this field is hidden)
               $('#specimen_id').html('<option value="0">No discipline selected</option>');
               $('#specimen_id').selectpicker('refresh');
               $('#specimen_id').selectpicker('render');

               // Update discipline selectfield
               var html= "";
               for (var discipline of data.disciplines_performed) {
                    html += '<option value="'+discipline.id+'">'+discipline.name+'</option>';
               }
               $('#discipline').html(html);
               $('#discipline').selectpicker('refresh');
               $('#discipline').selectpicker('render');

            });
            return false;

      });
});


// When discipline is changed,
$(function() {
    $('#discipline').on('change', function() {
        var case_id = $('#case_id').val();
        var discipline = $(this).val();
        $('#specimens').DataTable().clear().draw();
        $('#tests').DataTable().clear().draw();
        $('#assay_id').prop('disabled', false);
        $('#assay_id').selectpicker('val', 0);
        if (discipline != 0) {
            $.getJSON('/tests/get_specimens/', {
                case_id: case_id,
                discipline: discipline,
                }, function(data) {

                // set the empty table message for specimens if there are no specimens for
                // this case and discipline

                if (data.specimens.length == 0) {
                    $('#specimens .dataTables_empty').html('There are no specimens for this discipline');
                } else {
                    for (var specimen of data.specimens) {
                        $('#specimens').DataTable().row.add([
                            specimen['id'],
                            specimen['accession_number'],
                            specimen['code'],
                            specimen['description'],
                            specimen['collection_date'],
                            specimen['collection_time'],
                            specimen['current_sample_amount'],
                            specimen['submitted_sample_amount'],
                            specimen['condition'],
                        ]).draw();
                        $('#specimens').DataTable().rows().nodes().to$().addClass('rows');
                    }

                    html = ""
                    for (var specimen of data.specimen_choices) {
                      html += '<option value="'+specimen.id+'">'+specimen.name+'</option>';
                    }
                   $('#specimen_id').html(html);
                   $('#specimen_id').selectpicker('refresh');
                   $('#specimen_id').selectpicker('render');
                }


                if (data.tests.length == 0) {
                    $('#tests .dataTables_empty').html('There are no tests assigned for this discipline');
                } else {
                    for (var test of data.tests) {
                        $('#tests').DataTable().row.add([
                            test['accession_number'],
                            test['code'],
                            test['description'],
                            test['assay'],
                            test['test_name'],
                            test['batch_id'],
                        ]).draw();
                        $('#tests').DataTable().rows().nodes().to$().addClass('rows');
                    }
                }

             assay_choices = ''
             for (var assay of data.assay_choices) {
                  assay_choices += '<option value="'+assay.id+'">'+assay.name+'</option>';
                }

            $('#assay_id').empty().append(assay_choices);
            $('#assay_id').selectpicker('refresh')
            $('#assay_id').selectpicker('render')
            });
            return false;
        } else {
            $('#specimens .dataTables_empty').html('No discipline selected');
            $('#assay_id').prop('disabled', true);
            $('#assay_id').selectpicker('refresh')
        }
    });
});


// When the "Testing to be performed" checkboxes are checked, add the options to the
// "Discipline" select field. Since a user can submit without selecting specimens or tests,

$('.check').on('click', function() {

    var discipline = $(this).attr('id')
    discipline = discipline.slice(0, 1).toUpperCase()+discipline.slice(1);
    if ($(this).is(':checked')) {
        html = $('#discipline').html();
        html += '<option value="'+discipline+'">'+discipline+'</option>'

        $('#discipline').html(html);
        //$('#discipline').val(0);
        $('#discipline').selectpicker('refresh');
        $('#discipline').selectpicker('render');
    } else {
        $('#discipline option[value='+discipline+']').remove();
        $('#discipline').selectpicker('refresh');
    }

    //var checked_arr = [];
    //$('.check').each(function() {
    //    if ($(this).is(':checked') == true) {
    //        checked_arr.push(true)
    //    }

    //alert(checked_arr);
    //if (checked_arr.length > 0) {
    //    $('#discipline').attr('disabled', false);
    //    $('#submit').attr('disabled', false);
    //} else {
    //    $('#discipline').attr('disabled', true);
    //    $('#submit').attr('disabled', true);
    //}
    //})
})


$('#specimens').on('click', 'tbody tr', function (e) {
    if ($('#discipline').val() != 0) {
        //alert($(this).attr('class').includes('table-active'));
        $(this).addClass('table-active').siblings().removeClass('table-active');
        var specimen_id = Object.values($('#specimens').DataTable().row(this).data())[0];
        $('#specimen_id').val(specimen_id);
        $('#specimen_id').selectpicker('refresh');
         $.getJSON('/tests/get_default_assays/', {
            specimen_id: specimen_id,
            }, function(data) {
                 $('#assay_id').val(data.assays);
                 $('#assay_id').selectpicker('refresh');
                 $('#assay_id').selectpicker('render');
            });

            return false;
    }
});


//$(document).ready(function () {
//    $('#specimen_id').selectpicker('hide');
////    var disabled = true;
////    $('.check').each(function () {
////        if ($(this).val()) {
////            disabled = false;
////        }
////    });
////    $('#discipline').prop('disabled', disabled);
//});
