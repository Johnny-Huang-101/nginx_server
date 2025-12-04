// Highlight rows if user status is blocked (red) or deactivated (grey)
$(document).ready(function() {
    $.each($('.datatable tbody tr'), function () {
        var status = $(this).find('td.user-status').text();
        if (status == 'Deactivated') {
            $(this).addClass('table-secondary');
        } else if (status == 'Blocked') {
             $(this).addClass('table-danger');
        }
    });

    $.each($('tbody td'), function () {
        if ($(this).text() == "None") {
            $(this).text("")
        }
    });

});