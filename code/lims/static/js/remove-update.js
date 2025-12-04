/*
This script hides the Update button depending on permissions in LIMS - For view.html
This hides the update, attach, and remove button
*/
document.addEventListener('DOMContentLoaded', function() {
    // tables that FLD permissions CAN update
    const fldUpdate = ["containers", "specimens", "tests", "batches", "results", "solvents_and_reagents"]
    // tables that Administrative and FLD CAN update
    const administrativeAndFld = ["reports", "records", "requests", "litigation_packets", "bookings", "cases","services", "returns"]

    // tables that Method Dev CAN update
    const methodDevelopmentUpdate = [
    "instruments",
    "reference_materials",
    "solvents_and_reagents",
    "standards_and_solutions",
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

    if(fldUpdate.includes(tableName)) {
        console.log(currentUser)
        if(currentUser != "Admin" && currentUser != "FLD") {
            document.getElementById(tableName + '-update').style.display = 'none'
            document.getElementById(tableName + '-attach').style.display = 'none'
            document.getElementById(tableName + '-remove').style.display = 'none'
        }
    } else if(methodDevelopmentUpdate.includes(tableName)) {
        if(currentUser != "Admin" && currentUser != "FLD-MethodDevelopment" && currentUser != "Owner" && currentUser != "FLD") {
            document.getElementById(tableName + '-update').style.display = 'none'
            document.getElementById(tableName + '-attach').style.display = 'none'
            document.getElementById(tableName + '-remove').style.display = 'none'
        }
    } else if(administrativeAndFld.includes(tableName)) {
        if(currentUser != "Admin" && currentUser != "FLD" && currentUser != "FLD-Administrative" && currentUser != "Owner") {
        document.getElementById(tableName + '-update').style.display = 'none'
        document.getElementById(tableName + '-attach').style.display = 'none'
        document.getElementById(tableName + '-remove').style.display = 'none'
        }
    } else if(methodDevelopmentOnly.includes(tableName)) {
        if(currentUser != "Admin" && currentUser != "FLD-MethodDevelopment" && currentUser != "Owner") {
        document.getElementById(tableName + '-update').style.display = 'none'
        document.getElementById(tableName + '-attach').style.display = 'none'
        document.getElementById(tableName + '-remove').style.display = 'none'
        }
    } else {
        if(currentUser != "Admin" && currentUser != "Owner") {
        document.getElementById(tableName + '-update').style.display = 'none'
        document.getElementById(tableName + '-attach').style.display = 'none'
        document.getElementById(tableName + '-remove').style.display = 'none'
        }
    }
})

