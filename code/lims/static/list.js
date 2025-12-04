
function initDataTable(table=none, length=100, dom='Brft', scrollY="60vh") {

    $('#populating').modal("show")
    let thead = table.find('thead')
    let header = thead.find('tr')
    let header_clone = thead.children('.filters')
    if (header_clone.length == 0) {
        let header_clone = header.clone(true).addClass('filters')
        header_clone.appendTo(thead);
    }
//        var div = $('.dataTables_scrollBody');
//        console.log(div.get(0).scrollWidth);
//        console.log(div.innerWidth());

    var dt = table.DataTable({
        dom: '<<"row"<"col-xl-8"B><"col"f>>>rt',
        buttons: [],
        scrollX: true,
        scrollY: scrollY,
        scrollCollapse: true,
        orderCellsTop: true,
        fixedHeader: true,
        pageLength: length,
        order: [],
        initComplete: function () {

            var api = this.api();

            // For each column

            if (header_clone.length == 0) {
                api
                    .columns()
                    .eq(0)
                    .each(function (colIdx) {
                        // Set the header cell to contain the input element
                        var cell = $('.filters th').eq(
                            $(api.column(colIdx).header()).index()
                        );
                        var title = $(cell).text();
                        $(cell).html('<input type="text" placeholder="' + title + '" style="width: 100%; border: 1px solid lightgray; border-radius: 5px;  "/>');

                        // On every keypress in this input
                        $(
                            'input',
                            $('.filters th').eq($(api.column(colIdx).header()).index())
                        )
                            .off('keyup change')
                            .on('change', function (e) {
                                // Get the search value
                                $(this).attr('title', $(this).val());
                                var regexr = '({search})'; //$(this).parents('th').find('select').val();

                                var cursorPosition = this.selectionStart;
                                // Search the column for that value
                            if (this.value != ' ' && this.value != '*' && this.value.slice(-1) != "!") {
                                 api
                                .column(colIdx)
                                .search(
                                    this.value != ''
                                        ? regexr.replace('{search}', '(((' + this.value + ')))')
                                        : '',
                                    this.value != '',
                                    this.value == ''
                                )
                                .draw();

                            } else if (this.value == ' ') {
                                api
                                .column(colIdx)
                                .search('^$', true, false )
                                .draw();
                            } else if (this.value == '*') {
                                api
                                .column(colIdx)
                                .search('^(?!\s*$).+', true, false )
                                .draw();
                            } else if (this.value.slice(-1) == "!") {
                              var value = this.value.slice(0,-1)
                              api
                                .column(colIdx)
                                .search('^'+value+'$', true, false)
//                                .data()
//                                .filter(function (d, idx) {
//                                    var re = ">(\\s*{value}\\s*)<"
//                                    re = re.replace('{value}', value)
//                                    const regex = RegExp(re)
//                                    console.log(regex)
//                                    var match = d.match(regex)
//                                    if (match) {
//                                    match = match[0]
//                                    .replace(">", "")
//                                    .replace("<", "")
//                                    .replaceAll("\n", "")
//                                    .trim()
//                                    console.log(match)
//                                    console.log(value)
//                                    console.log(match == value)
//                                    }
//                                    return d
//                                })
                                .draw();
                             }

//                             var body = table.body();
//                             body.unhighlight();
//                             if (this.value.slice(-1) == '!') {
//                                body.highlight( this.value.slice(0,-1))
//                             } else {
//                                body.highlight( this.value );
//                             }
                                $('#first').html('1');
                                $('#last').html(api.page.info().recordsDisplay);

                                if (api.page.info().recordsDisplay != length) {
                                    $('#filtered').removeAttr('hidden');
                                } else if (api.page.info().recordsDisplay == -1) {
                                    $('#filtered').attr('hidden', true);
                                } else {
                                    $('#filtered').attr('hidden', true);
                                 }
                            })
                            .on('keyup', function (e) {
                                e.stopPropagation();

                                $(this).trigger('change');
                                $(this)
                                    .focus()[0]
                                    .setSelectionRange(this.selectionStart, this.selectionStart);
                            });
                    });
                }
        api.columns.adjust();
        $('#table-div').css('display', 'block');
        $('#spinner-div').hide();
        $('#populating').modal('hide')
        $('#buttons').prependTo(".dt-buttons")

        $('#go-to-page').on('click', function() {
            var pageNum = $('#page-num').val();
            if (query != 'None') {
                window.location.href =table_name+'?query_type='+query_type+'&query='+query+'%page='+pageNum+'&length='+length;
            } else {
                window.location.href =table_name+'?page='+pageNum+'&length='+length;
            }
        });
        },
    });
}


// On page load, adjust columns
//window.onload = function(){
//    $($.fn.dataTable.tables(true)).DataTable().columns.adjust();
//}

//$(document).ready(function(){
//    $($.fn.dataTable.tables(true)).DataTable().columns.adjust();
//})

//Style table rows
$(document).ready(function StyleTableRows() {
    $.each($('.datatable tbody tr'), function () {
        // For items which have a db_status of 'Removed', hide the rows
        // if the current_user does not have 'Admin' or 'Owner' permissions.
        // If admin and above, highlight the rows grey (i.e. table-secondary bootstrap class)
        var status = $(this).find('td.db-status').text();
        if (status == 'Removed') {
            if (!['Admin', 'Owner'].includes(permissions)) {
                $(this).hide();
            } else {
                $(this).addClass('table-secondary');
            }
        // If an item is pending removal (db_status == 'Removal Pending') highlight
        // row red (i.e. table-danger bootstrap class)
        } else if (status == 'Removal Pending') {
             $(this).addClass('table-danger');
        // if an item is pending, highlight the row yellow (i.e., table-warning bootstrap class)
        } else if (['Pending', 'Active With Pending Changes', 'Changes Pending'].includes(status)) {
            $(this).addClass('table-primary');
        }
        // Highlight locked columns
        var locked = $(this).find('td.locked').text().trim() //locked generates a lot of white space, trim removes it
        if (locked != "") {
          $(this).addClass('table-primary');
        }
    });

    //Remove None values, trim() is needed for hyperlinked None
    $.each($('tbody td'), function () {
        if ($(this).text().trim() == "None") {
            $(this).text("")
        }
    });

});

$(window).on('load', function() {
    // Add a 20-millisecond delay before simulating the click
    if ($('#click').length) {
        $('.spinner-border').show();
        setTimeout(function() {
            $('#click').trigger('click');
            $('.spinner-border').hide();
        }, 1);
    }
});

//$(document).ready( function () {
//    new DataTable($('.datatable'));
//    var table = .dataTable().on( 'draw', function () {
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
