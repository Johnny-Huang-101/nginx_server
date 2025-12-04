
$(document).ready(function() {
    collapseSection();
//    setLocalStorage();
    expandSidebar();
    collapseSidebar();
});

//function collapseSection() {
//    $(".collapse-toggle").each(function() {
//        if (localStorage.getItem("coll_" + this.id) === "true") {
//            $(this).addClass("collapse");
//        } else {
//            $(this).removeClass("collapse");
//        }
//    });
//}

//$(function () {
//    //If shown.bs.collapse add the unique id to local storage
//    $(".collapse-toggle").on("shown.bs.collapse", function () {
//        localStorage.setItem("coll_" + this.id, true);
//        $(this).addClass('show');
//        localStorage.ClassName = "show";
//        $(this).removeClass('collapse');
//
//    });
//
//    //If hidden.bs.collaspe remove the unique id from local storage
//    $(".collapse-toggle").on("hidden.bs.collapse", function () {
//        localStorage.removeItem("coll_" + this.id);
//        $(this).addClass('collapse');
//        localStorage.ClassName = "collapse";
//        $(this).removeClass('show');
//    });
//
//    //If the key exists and is set to true, show the collapsed, otherwise hide
//    $(".collapse-toggle").each(function () {
//
//        if (localStorage.getItem("coll_" + this.id) == "true") {
//            $(this).addClass("collapse")
//            $(this).collapse("show");
//            $(this).addClass(localStorage.ClassName);
//
//        }
//        else {
//            $(this).removeClass("collapse")
//            $(this).collapse("hide");
//            $(this).addClass(localStorage.ClassName);
//
//        }
//    });
//});

//function setLocalStorage() {
//    // Get scroll position from localStorage
////    var scrollpos = localStorage.getItem('scrollpos');
//
//    $(".collapse-toggle").on("shown.bs.collapse", function() {
//        localStorage.setItem("coll_" + this.id, true);
//    });
//
//    $(".collapse-toggle").on("hidden.bs.collapse", function() {
//        localStorage.removeItem("coll_" + this.id);
//    });
//
////    document.addEventListener("DOMContentLoaded", function(event) {
////        // Scroll to the position stored in localStorage
////        if (scrollpos) window.scrollTo(0, parseInt(scrollpos));
////    });
//
////    window.onbeforeunload = function(e) {
////        // Store current scroll position in localStorage
////        localStorage.setItem('scrollpos', window.scrollY);
////    };
//}

function expandSidebar() {
    $('#expand').on('click', function () {
        $('.coll-toggle').each(function () {
            $(this).toggleClass('collapse')
        });
    });
}

function collapseSidebar() {
    $('#collapse').on('click', function () {
        $('.coll-toggle').each(function () {
            $(this).toggleClass('collapse')
        });
    });
}



$('.chevron').on('click', function() {
    console.log('chevron')
    if ($(this).hasClass('fa-chevron-right')) {
        $(this).removeClass('fa-chevron-right')
        $(this).addClass('fa-chevron-down');
    } else {
        $(this).removeClass('fa-chevron-down')
        $(this).addClass('fa-chevron-right');
    }
});


// Set the settings for the flash messaging.
//Stay for 5 seconds, then slide up over 0.5s
$(document).ready(function(){
    $(".flash-alert").delay(5000).slideUp(500);
});


// If the sidebar is collapsed or expanded, adjust any datatable columns
$(document).ready(function(){
    $('#x-sidebar-toggle').on('click', function () {
       $($.fn.dataTable.tables(true)).DataTable().columns.adjust();
    });

    $('.all-drops-collapse').on('click', function () {
       $($.fn.dataTable.tables(true)).DataTable().columns.adjust();
    });
});


// If a datatable is in a collapsible card (e.g. accordion)
// when that card is expanded, adjust the tables columns
$(document).ready(function(){
    $('.collapse').on('shown.bs.collapse', function () {
       $($.fn.dataTable.tables(true)).DataTable()
          .columns.adjust();
    });
});


$('[data-toggle="tooltip"]').tooltip({
    content: function() {
        return $(this).prop('title');
    }
});


$(document).ready(function () {
    $('#view_review').on('shown.bs.modal', function (event) {
        // Optionally get the triggering element if available.
        var trigger = event.relatedTarget;
        // Try to get values from the trigger; if not available, assign defaults.
        let pend = trigger ? $(trigger).parents('tr').find('td.pending-submitter').html() : '';
        console.log('Pending submitter: ', pend);
        let func = 'Review';
        var case_number = trigger ? $(trigger).attr('name') : '';
        var case_id = trigger ? $(trigger).attr('value') : '';


        // If case_id is not found (falsy), use session['pending_case_id'].
        if (!case_id) {
            case_id = pendingCaseIdFromSession;
        }

        if (pend == '{{current_user.initials}}') {
            func = 'Edit';
        }
        console.log(func);

        $('.func_text').html(func);
        $('.view-only').attr('href', "cases/" + case_id + "?view_only=True");
        $('#proceed').attr('href', "cases/" + case_id);
        $('.modal-case-number').html(case_number);

        // Get disciplines of submitted evidence for the case
        if (case_id) {
            $.getJSON('/cases/get_case_evidence_disciplines/', { case_id: case_id }, function(data) {
                var HTML = '';
                for (var choice of data.choices) {
                    HTML += '<option value="' + choice.id + '">' + choice.name + '</option>';
                }
                $('#discipline-select').html(HTML);
            });
        }

        // Set default URL for 'Review' and 'View Only' buttons.
        $('#edit-review-custody').attr('href', "cases/" + case_id);
        $('#view-only').attr('href', "cases/" + case_id + "?view_only=True");
        $('#edit-review-no-custody').attr('href', "cases/" + case_id + "?custody=0");

        // Change the URL of the Review button based on the discipline selection.
        $('#discipline-select').on('change', function () {
            var discipline = $('#discipline-select').val();
            if (discipline) {
                $('#edit-review-custody').attr('href', "cases/" + case_id + "?review_discipline=" + discipline + "&custody=1");
                $('#edit-review-no-custody').attr('href', "cases/" + case_id + "?review_discipline=" + discipline + "&custody=0");
            } else {
                $('#edit-review-custody').attr('href', "cases/" + case_id);
                $('#edit-review-no-custody').attr('href', "cases/" + case_id + "?custody=0");
            }
        });
    });
});


$(document).ready(function () {
    $('#locking').on('shown.bs.modal', function (event) {
        // Optionally get the triggering element if available.
        var trigger = event.relatedTarget;
        // Try to get values from the trigger; if not available, assign defaults.
        let pend = trigger ? $(trigger).parents('tr').find('td.pending-submitter').html() : '';
        console.log('Pending submitter: ', pend);
        let func = 'Review';
        var case_number = trigger ? $(trigger).attr('name') : '';
        var case_id = trigger ? $(trigger).attr('value') : '';


        // If case_id is not found (falsy), use session['pending_case_id'].
        if (!case_id) {
            case_id = pendingCaseIdFromSession;
        }

        if (pend == '{{current_user.initials}}') {
            func = 'Edit';
        }
        console.log(func);

        $('.func_text').html(func);
        $('.view-only').attr('href', "cases/" + case_id + "?view_only=True");
        $('#proceed').attr('href', "cases/" + case_id);
        $('.modal-case-number').html(case_number);

        // Get disciplines of submitted evidence for the case
        if (case_id) {
            $.getJSON('/cases/get_case_evidence_disciplines/', { case_id: case_id }, function(data) {
                var HTML = '';
                for (var choice of data.choices) {
                    HTML += '<option value="' + choice.id + '">' + choice.name + '</option>';
                }
                $('#discipline-select').html(HTML);
            });
        }

        // Set default URL for 'Review' and 'View Only' buttons.
        $('#edit-review-custody').attr('href', "cases/" + case_id + "?custody=1");
        $('#view-only').attr('href', "cases/" + case_id + "?view_only=True");
        $('#edit-review-no-custody').attr('href', "cases/" + case_id + "?custody=0");

        // Change the URL of the Review button based on the discipline selection.
        $('#discipline-select').on('change', function () {
            var discipline = $('#discipline-select').val();
            if (discipline) {
                $('#edit-review-custody').attr('href', "cases/" + case_id + "?review_discipline=" + discipline + "&custody=1");
                $('#edit-review-no-custody').attr('href', "cases/" + case_id + "?review_discipline=" + discipline + "&custody=0");
            } else {
                $('#edit-review-custody').attr('href', "cases/" + case_id);
                $('#edit-review-no-custody').attr('href', "cases/" + case_id + "?custody=0");
            }
        });
    });
});
