//$(document).ready( function () {
// var table = $('.view-table').DataTable();
// table.on( 'draw', function () {
//        var body = $( table.table().body() );
//        body.unhighlight();
//        body.highlight( table.search() );
//        //Remove None values
////        Explicit removal of None values does not work on hyperlinks
//        if ($(this).text() == "None") {
//            $(this).text("")
//        }
////         This works on hyperlinks but will remove "None" in any string including
////        None Detected in Components
//
////        if ($(this).text().includes("None")) {
////            $(this).text("")
////        }
//
//    });
// });


$(document).ready(function () {
    console.log(pending_fields)
    $('.form-item').each(function () {
        let name = $(this).prop('id')
        console.log(name)
        if (pending_fields.includes(name)) {
            $(this).addClass('table-warning');
        } else {
            if ($(this).hasClass('t-tip')) {
                $(this).removeClass('t-tip')
            } else {
                $(this).find('A').removeClass('t-tip')
            }
        }
    });
});

//Remove None values from tables
$.each($('tbody td'), function () {
    if ($(this).text().trim() == "None") {
        $(this).text("")
    }
});

$('.selectpicker').selectpicker({
    "liveSearch": true,
    "selectedTextFormat": "count > 10",
});