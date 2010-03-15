$(function () {
  $('.toggle').click(function () {
    var el = $($(this).attr('toggle-el'));
    el.slideToggle();
  });
});
