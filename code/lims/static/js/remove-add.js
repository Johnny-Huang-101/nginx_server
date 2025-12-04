// This script hides the Add button depending on permission in LIMS - for list.html
document.addEventListener('DOMContentLoaded', function() {

    const tableNames = ["cases", "containers", "specimens", "tests", "batches", "results"]
    // Areas where Administrative and FLD can Add
    const administrativeAndFld = ["reports", "records", "requests", "litigation_packets", "bookings", "services", "personnel", "returns"]

    // Areas where only Method Dev can Add
    const methodDevelopmentAndFldAdd = [
    "standards_and_solutions",
    "reference_materials",
    "solvents_and_reagents"
    ]

    const methodDevelopmentOnly = [
    "solvents_and_reagents",
    "standards_and_solutions",
    "reference_materials",
    "instruments",
    "rooms",
    "cabinets",
    "benches",
    "storage",
    "compactors",
    "cooled_storage",
    "evidence_lockers",
    "general_labware",
    "calibrated_labware",
    "hubs",
    "probes",
    "histology_equipment",
    "services"
    ]

    const mariaPermissions = [
        "compounds"
    ]

    if(tableNames.includes(tableName)) {
        /*
        Removes Add button for specific pages for specific permissions
        */
        if(currentUser != "Admin" && currentUser != "FLD" && currentUser != "Owner") {
        document.getElementById(table_name + '-add').style.display = 'none'
        }
    } else if(administrativeAndFld.includes(tableName)) {
        if(currentUser != "Admin" && currentUser != "FLD" && currentUser != "FLD-Administrative" && currentUser != "Owner") {
        document.getElementById(table_name + '-add').style.display = 'none'
        }
    } else if (methodDevelopmentAndFldAdd.includes(tableName)) {
        if(currentUser != "Admin" && currentUser != "FLD-MethodDevelopment" && currentUser != "Owner" && currentUser != "FLD") {
        document.getElementById(table_name + '-add').style.display = 'none'
        }
    } else if(methodDevelopmentOnly.includes(tableName)) {
    if(currentUser != "Admin" && currentUser != "FLD-MethodDevelopment" && currentUser != "Owner") {
        document.getElementById(table_name + '-add').style.display = 'none'
        }
    } 
    else if(mariaPermissions.includes(tableName)) {
        if(currentUserInitials == 'MVS') {

            document.getElementById(table_name + '-add').style.display = 'inline-block'
        }

    } else {
        /*
        For general pages where only Admins can add
        */
        if(currentUser != "Admin" && currentUser != "Owner") {
        document.getElementById(table_name + '-add').style.display = 'none'
    }
    }
})

