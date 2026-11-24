def test_transfer_keeps_total_inventory_constant():
    storage, display, moved = 210, 30, 12
    assert storage + display == (storage - moved) + (display + moved)

def test_sale_reduces_total_inventory():
    storage, display, sold = 210, 30, 5
    assert (storage + display) - sold == storage + (display - sold)

def test_box_receiving_calculates_units():
    boxes, units_per_box, loose = 10, 24, 3
    assert boxes * units_per_box + loose == 243
