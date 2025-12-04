
// highlight row color based on status. Add the "item-status" class to the <td> tag
// i.e. <td class='item-status'>{{item.status.name}}</td>
$(document).ready(function () {
    $.each($('.datatable tbody tr'), function () {
        // Highlight rows based on status
        // Inactive = Grey (secondary)
        // Out of Service = Yellow (warning)
        // Obsolete = Grey with white text (dark)
        var status = $(this).find('td.item-status').text();
        console.log(status);
        if (status == 'Inactive') {
            $(this).addClass('table-primary')
        } else if (status == 'Out of Service') {
            $(this).addClass('table-warning')
        } else if (status == 'Obsolete') {
          $(this).addClass('table-secondary')
        }
    });
});
